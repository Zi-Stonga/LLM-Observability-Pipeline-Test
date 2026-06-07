"""
AI Observability CDK Stack.

Provisions all AWS infrastructure for the LLM observability pipeline:
API Gateway, Lambda (x6), DynamoDB (x4), Kinesis, Firehose, SQS+DLQ,
SNS, S3, CloudWatch dashboards/alarms, WAFv2, and KMS encryption.

Deploy:
    cdk deploy -c alert_email=you@example.com -c allowed_origins=https://app.example.com
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigateway as apigw,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_kinesis as kinesis,
    aws_kinesisfirehose as firehose,
    aws_kms as kms,
    aws_lambda as lambda_,
    aws_lambda_event_sources as lambda_events,
    aws_logs as logs,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as sns_subs,
    aws_sqs as sqs,
    aws_wafv2 as wafv2,
)
from constructs import Construct

_LAMBDA_RUNTIME = lambda_.Runtime.PYTHON_3_12
_CW_NAMESPACE = "AIObservability"


class AiObservabilityStack(Stack):
    """Root CDK stack for the LLM observability pipeline."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs: object) -> None:
        super().__init__(scope, construct_id, **kwargs)

        alert_email = self._require_context("alert_email")
        cors_origins = self._require_origins()

        storage_key = self._make_kms_key("StorageKey", "DynamoDB + S3 + SQS + SNS")
        stream_key = self._make_kms_key("StreamKey", "Kinesis stream")

        raw_bucket = self._make_bucket(storage_key)
        tables = self._make_tables(storage_key)
        span_stream = self._make_kinesis(stream_key)
        self._make_firehose(raw_bucket, span_stream, storage_key, stream_key)
        scoring_dlq, scoring_queue = self._make_queues(storage_key)
        alert_topic = self._make_sns(alert_email, storage_key)

        roles = self._make_roles(tables, span_stream, scoring_queue, scoring_dlq,
                                  raw_bucket, alert_topic, storage_key, stream_key)

        fns = self._make_lambdas(roles, tables, span_stream, scoring_queue, alert_topic)
        self._wire_event_sources(fns, span_stream, scoring_queue, tables["scores"])

        api = self._make_api(fns, cors_origins)
        self._make_waf(api)
        self._make_dashboard(scoring_dlq)
        self._make_alarms(alert_topic, scoring_dlq)

        logs.LogGroup(
            self, "TraceLogGroup",
            log_group_name="/ai-obs/traces",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        cdk.CfnOutput(self, "ApiEndpoint", value=api.url)
        cdk.CfnOutput(self, "RawBucket", value=raw_bucket.bucket_name)
        cdk.CfnOutput(self, "AlertTopicArn", value=alert_topic.topic_arn)
        cdk.CfnOutput(self, "ScoringDLQUrl", value=scoring_dlq.queue_url)
        cdk.CfnOutput(self, "StorageKeyArn", value=storage_key.key_arn)
        cdk.CfnOutput(
            self, "DashboardUrl",
            value=(
                f"https://{self.region}.console.aws.amazon.com"
                "/cloudwatch/home#dashboards:name=AI-Pipeline-Observability"
            ),
        )

    # --------------------------------------------------------------------------
    # Context helpers
    # --------------------------------------------------------------------------

    def _require_context(self, key: str) -> str:
        value = self.node.try_get_context(key)
        if not value:
            raise ValueError(
                f"CDK context key '{key}' is required. "
                f"Pass -c {key}=<value> to cdk deploy."
            )
        return str(value)

    def _require_origins(self) -> list[str]:
        raw = self.node.try_get_context("allowed_origins") or ""
        origins = [o.strip() for o in str(raw).split(",") if o.strip()]
        if not origins:
            raise ValueError(
                "CDK context key 'allowed_origins' is required (comma-separated). "
                "Pass -c allowed_origins=https://your-app.example.com"
            )
        return origins

    # --------------------------------------------------------------------------
    # Resource factories
    # --------------------------------------------------------------------------

    def _make_kms_key(self, construct_id: str, purpose: str) -> kms.Key:
        """Create a CMK with automatic rotation for the given purpose."""
        return kms.Key(
            self, construct_id,
            description=f"AI Obs pipeline: {purpose} encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.RETAIN,
        )

    def _make_bucket(self, key: kms.Key) -> s3.Bucket:
        """Create the raw trace archive bucket with encryption and access controls."""
        return s3.Bucket(
            self, "RawTraceBucket",
            bucket_name=f"ai-obs-raw-traces-{self.account}-{self.region}",
            versioned=True,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=key,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="Glacier",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90),
                        )
                    ],
                )
            ],
            removal_policy=RemovalPolicy.RETAIN,
        )

    def _make_tables(self, key: kms.Key) -> dict[str, dynamodb.Table]:
        """Create all four DynamoDB tables with streams and encryption."""
        enc = dynamodb.TableEncryption.CUSTOMER_MANAGED

        trace = dynamodb.Table(
            self, "TraceTable",
            table_name="ai-obs-traces",
            partition_key=dynamodb.Attribute(name="trace_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="span_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            time_to_live_attribute="ttl",
            encryption=enc,
            encryption_key=key,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
        )
        trace.add_global_secondary_index(
            index_name="session-index",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.STRING
            ),
        )

        scores = dynamodb.Table(
            self, "ScoresTable",
            table_name="ai-obs-scores",
            partition_key=dynamodb.Attribute(name="trace_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            encryption=enc,
            encryption_key=key,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        flags = dynamodb.Table(
            self, "FlagsTable",
            table_name="ai-obs-flags",
            partition_key=dynamodb.Attribute(name="flag_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="trace_id", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=enc,
            encryption_key=key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        prompts = dynamodb.Table(
            self, "PromptRegistry",
            table_name="ai-obs-prompts",
            partition_key=dynamodb.Attribute(name="prompt_id", type=dynamodb.AttributeType.STRING),
            sort_key=dynamodb.Attribute(name="version", type=dynamodb.AttributeType.STRING),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=enc,
            encryption_key=key,
            removal_policy=RemovalPolicy.DESTROY,
        )

        return {"trace": trace, "scores": scores, "flags": flags, "prompts": prompts}

    def _make_kinesis(self, key: kms.Key) -> kinesis.Stream:
        """Create the span stream with 7-day retention and KMS encryption."""
        return kinesis.Stream(
            self, "SpanStream",
            stream_name="ai-obs-spans",
            shard_count=2,
            retention_period=Duration.hours(168),
            encryption=kinesis.StreamEncryption.KMS,
            encryption_key=key,
        )

    def _make_firehose(
        self,
        bucket: s3.Bucket,
        stream: kinesis.Stream,
        storage_key: kms.Key,
        stream_key: kms.Key,
    ) -> None:
        """Create the Kinesis Firehose delivery stream to S3."""
        role = iam.Role(
            self, "FirehoseRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
        )
        bucket.grant_write(role)
        stream.grant_read(role)
        storage_key.grant_encrypt_decrypt(role)
        stream_key.grant_decrypt(role)

        firehose.CfnDeliveryStream(
            self, "SpanFirehose",
            delivery_stream_name="ai-obs-span-firehose",
            kinesis_stream_source_configuration=firehose.CfnDeliveryStream.KinesisStreamSourceConfigurationProperty(
                kinesis_stream_arn=stream.stream_arn,
                role_arn=role.role_arn,
            ),
            s3_destination_configuration=firehose.CfnDeliveryStream.S3DestinationConfigurationProperty(
                bucket_arn=bucket.bucket_arn,
                role_arn=role.role_arn,
                prefix="spans/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/",
                error_output_prefix="errors/!{firehose:error-output-type}/",
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=60, size_in_m_bs=5
                ),
                compression_format="GZIP",
                encryption_configuration=firehose.CfnDeliveryStream.EncryptionConfigurationProperty(
                    kms_encryption_config=firehose.CfnDeliveryStream.KMSEncryptionConfigProperty(
                        awskms_key_arn=storage_key.key_arn
                    )
                ),
            ),
        )

    def _make_queues(self, key: kms.Key) -> tuple[sqs.Queue, sqs.Queue]:
        """Create the scoring queue and its dead-letter queue, both encrypted."""
        dlq = sqs.Queue(
            self, "ScoringDLQ",
            queue_name="ai-obs-scoring-dlq",
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=key,
            retention_period=Duration.days(14),
        )
        queue = sqs.Queue(
            self, "ScoringQueue",
            queue_name="ai-obs-scoring-queue",
            visibility_timeout=Duration.seconds(120),
            encryption=sqs.QueueEncryption.KMS,
            encryption_master_key=key,
            dead_letter_queue=sqs.DeadLetterQueue(max_receive_count=3, queue=dlq),
        )
        return dlq, queue

    def _make_sns(self, alert_email: str, key: kms.Key) -> sns.Topic:
        """Create the SNS alert topic with email subscription."""
        topic = sns.Topic(
            self, "AlertTopic",
            topic_name="ai-obs-alerts",
            display_name="AI Observability Alerts",
            master_key=key,
        )
        topic.add_subscription(sns_subs.EmailSubscription(alert_email))
        return topic

    def _cw_put_policy(self) -> iam.PolicyStatement:
        """Return a namespace-scoped CloudWatch PutMetricData policy statement."""
        return iam.PolicyStatement(
            actions=["cloudwatch:PutMetricData"],
            resources=["*"],
            conditions={"StringEquals": {"cloudwatch:namespace": _CW_NAMESPACE}},
        )

    def _make_roles(
        self,
        tables: dict[str, dynamodb.Table],
        stream: kinesis.Stream,
        queue: sqs.Queue,
        dlq: sqs.Queue,
        bucket: s3.Bucket,
        topic: sns.Topic,
        storage_key: kms.Key,
        stream_key: kms.Key,
    ) -> dict[str, iam.Role]:
        """Create six least-privilege IAM roles, one per Lambda function."""
        base = [iam.ManagedPolicy.from_aws_managed_policy_name(
            "service-role/AWSLambdaBasicExecutionRole"
        )]
        cw = self._cw_put_policy()

        def role(id_: str) -> iam.Role:
            return iam.Role(
                self, id_,
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                managed_policies=base,
            )

        ingest = role("IngestRole")
        tables["trace"].grant_write_data(ingest)
        stream.grant_write(ingest)
        tables["prompts"].grant_read_data(ingest)
        storage_key.grant_encrypt_decrypt(ingest)
        stream_key.grant_encrypt(ingest)

        processor = role("ProcessorRole")
        stream.grant_read(processor)
        tables["trace"].grant_write_data(processor)
        queue.grant_send_messages(processor)
        storage_key.grant_encrypt_decrypt(processor)
        stream_key.grant_decrypt(processor)

        scorer = role("ScorerRole")
        tables["trace"].grant_read_data(scorer)
        tables["scores"].grant_write_data(scorer)
        queue.grant_consume_messages(scorer)
        storage_key.grant_encrypt_decrypt(scorer)
        scorer.add_to_policy(cw)

        flagging = role("FlaggingRole")
        tables["trace"].grant_read_data(flagging)
        tables["scores"].grant_stream_read(flagging)
        tables["flags"].grant_write_data(flagging)
        topic.grant_publish(flagging)
        storage_key.grant_encrypt_decrypt(flagging)
        flagging.add_to_policy(cw)

        feedback = role("FeedbackRole")
        tables["scores"].grant_write_data(feedback)
        tables["flags"].grant_write_data(feedback)
        storage_key.grant_encrypt_decrypt(feedback)
        feedback.add_to_policy(cw)

        metrics = role("MetricsRole")
        tables["trace"].grant_read_data(metrics)
        storage_key.grant_decrypt(metrics)
        metrics.add_to_policy(cw)

        return {
            "ingest": ingest,
            "processor": processor,
            "scorer": scorer,
            "flagging": flagging,
            "feedback": feedback,
            "metrics": metrics,
        }

    def _make_lambdas(
        self,
        roles: dict[str, iam.Role],
        tables: dict[str, dynamodb.Table],
        stream: kinesis.Stream,
        queue: sqs.Queue,
        topic: sns.Topic,
    ) -> dict[str, lambda_.Function]:
        """Create all six Lambda functions with X-Ray tracing enabled."""
        base_env = {
            "TRACE_TABLE": tables["trace"].table_name,
            "SCORES_TABLE": tables["scores"].table_name,
            "FLAGS_TABLE": tables["flags"].table_name,
            "ALERT_TOPIC_ARN": topic.topic_arn,
        }

        def fn(
            id_: str,
            name: str,
            handler: str,
            asset: str,
            env: dict[str, str],
            role: iam.Role,
            timeout: int = 30,
            memory: int = 256,
        ) -> lambda_.Function:
            return lambda_.Function(
                self, id_,
                function_name=name,
                runtime=_LAMBDA_RUNTIME,
                handler=handler,
                code=lambda_.Code.from_asset(asset),
                role=role,
                timeout=Duration.seconds(timeout),
                memory_size=memory,
                environment=env,
                tracing=lambda_.Tracing.ACTIVE,
            )

        ingest = fn(
            "IngestFn", "ai-obs-ingest", "ingest.handler",
            "cdk_stack/lambda/ingest",
            {**base_env, "SPAN_STREAM": stream.stream_name,
             "PROMPT_REGISTRY": tables["prompts"].table_name},
            roles["ingest"],
        )
        processor = fn(
            "SpanProcessorFn", "ai-obs-span-processor", "processor.handler",
            "cdk_stack/lambda/processor",
            {**base_env, "SCORING_QUEUE_URL": queue.queue_url},
            roles["processor"], timeout=60, memory=512,
        )
        scorer = fn(
            "ScorerFn", "ai-obs-scorer", "scorer.handler",
            "cdk_stack/lambda/scorer",
            base_env, roles["scorer"], timeout=120, memory=512,
        )
        flagging = fn(
            "FlaggingFn", "ai-obs-flagging", "flagging.handler",
            "cdk_stack/lambda/flagging",
            base_env, roles["flagging"], timeout=60,
        )
        feedback = fn(
            "FeedbackFn", "ai-obs-feedback", "feedback.handler",
            "cdk_stack/lambda/feedback",
            base_env, roles["feedback"], timeout=30, memory=128,
        )
        metrics_fn = fn(
            "MetricsFn", "ai-obs-metrics", "metrics.handler",
            "cdk_stack/lambda/metrics",
            base_env, roles["metrics"], timeout=300, memory=512,
        )

        rule = events.Rule(
            self, "MetricsSchedule",
            rule_name="ai-obs-metrics-schedule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
        )
        rule.add_target(targets.LambdaFunction(metrics_fn))

        return {
            "ingest": ingest,
            "processor": processor,
            "scorer": scorer,
            "flagging": flagging,
            "feedback": feedback,
            "metrics": metrics_fn,
        }

    def _wire_event_sources(
        self,
        fns: dict[str, lambda_.Function],
        stream: kinesis.Stream,
        queue: sqs.Queue,
        scores_table: dynamodb.Table,
    ) -> None:
        """Attach Kinesis, SQS, and DynamoDB Streams event sources."""
        fns["processor"].add_event_source(
            lambda_events.KinesisEventSource(
                stream,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=50,
                bisect_batch_on_error=True,
                retry_attempts=3,
            )
        )
        fns["scorer"].add_event_source(
            lambda_events.SqsEventSource(queue, batch_size=5)
        )
        fns["flagging"].add_event_source(
            lambda_events.DynamoEventSource(
                scores_table,
                starting_position=lambda_.StartingPosition.LATEST,
                batch_size=10,
                bisect_batch_on_function_error=True,
                retry_attempts=3,
            )
        )

    def _make_api(
        self,
        fns: dict[str, lambda_.Function],
        cors_origins: list[str],
    ) -> apigw.RestApi:
        """Create API Gateway with access logging, throttling, and scoped CORS."""
        api = apigw.RestApi(
            self, "ObsApi",
            rest_api_name="ai-observability-api",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=cors_origins,
                allow_methods=["POST", "OPTIONS"],
                allow_headers=["Content-Type", "X-Api-Key"],
                max_age=Duration.hours(1),
            ),
            deploy_options=apigw.StageOptions(
                stage_name="v1",
                throttling_rate_limit=1000,
                throttling_burst_limit=200,
                logging_level=apigw.MethodLoggingLevel.INFO,
                metrics_enabled=True,
                tracing_enabled=True,
                access_log_destination=apigw.LogGroupLogDestination(
                    logs.LogGroup(
                        self, "ApiAccessLog",
                        log_group_name="/ai-obs/api-access",
                        retention=logs.RetentionDays.THREE_MONTHS,
                        removal_policy=RemovalPolicy.DESTROY,
                    )
                ),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True, http_method=True, ip=True, protocol=True,
                    request_time=True, resource_path=True, response_length=True,
                    status=True, user=True,
                ),
            ),
        )

        traces_r = api.root.add_resource("traces")
        traces_r.add_method(
            "POST", apigw.LambdaIntegration(fns["ingest"]), api_key_required=True
        )

        feedback_r = api.root.add_resource("feedback")
        feedback_r.add_method(
            "POST", apigw.LambdaIntegration(fns["feedback"]), api_key_required=True
        )

        api_key = api.add_api_key("ObsApiKey", api_key_name="ai-obs-api-key")
        plan = api.add_usage_plan(
            "ObsUsagePlan",
            name="ai-obs-usage-plan",
            throttle=apigw.ThrottleSettings(rate_limit=1000, burst_limit=200),
        )
        plan.add_api_key(api_key)
        plan.add_api_stage(stage=api.deployment_stage)

        return api

    def _make_waf(self, api: apigw.RestApi) -> None:
        """Attach WAFv2 WebACL with OWASP managed rules and IP rate limiting."""
        waf = wafv2.CfnWebACL(
            self, "ApiWaf",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="ai-obs-waf",
                sampled_requests_enabled=True,
            ),
            rules=[
                self._waf_managed_rule("CommonRuleSet", 1, "AWSManagedRulesCommonRuleSet"),
                self._waf_managed_rule("KnownBadInputs", 2, "AWSManagedRulesKnownBadInputsRuleSet"),
                self._waf_rate_rule("IPRateLimit", 3, limit=2000),
            ],
        )
        wafv2.CfnWebACLAssociation(
            self, "ApiWafAssociation",
            resource_arn=(
                f"arn:aws:apigateway:{self.region}::"
                f"/restapis/{api.rest_api_id}/stages/v1"
            ),
            web_acl_arn=waf.attr_arn,
        )

    def _waf_managed_rule(
        self, name: str, priority: int, managed_name: str
    ) -> wafv2.CfnWebACL.RuleProperty:
        return wafv2.CfnWebACL.RuleProperty(
            name=name,
            priority=priority,
            override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                    vendor_name="AWS", name=managed_name
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=name,
                sampled_requests_enabled=True,
            ),
        )

    def _waf_rate_rule(
        self, name: str, priority: int, limit: int
    ) -> wafv2.CfnWebACL.RuleProperty:
        return wafv2.CfnWebACL.RuleProperty(
            name=name,
            priority=priority,
            action=wafv2.CfnWebACL.RuleActionProperty(block={}),
            statement=wafv2.CfnWebACL.StatementProperty(
                rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                    limit=limit, aggregate_key_type="IP"
                )
            ),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=name,
                sampled_requests_enabled=True,
            ),
        )

    def _make_dashboard(self, dlq: sqs.Queue) -> None:
        """Create the CloudWatch operations dashboard."""
        ns = _CW_NAMESPACE
        dashboard = cloudwatch.Dashboard(
            self, "ObsDashboard", dashboard_name="AI-Pipeline-Observability"
        )
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Requests/min",
                left=[cloudwatch.Metric(namespace=ns, metric_name="RequestCount",
                      statistic="Sum", period=Duration.minutes(1))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Avg Latency (ms)",
                left=[cloudwatch.Metric(namespace=ns, metric_name="PipelineLatencyMs",
                      statistic="Average", period=Duration.minutes(1))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Hallucination Score",
                left=[cloudwatch.Metric(namespace=ns, metric_name="HallucinationScore",
                      statistic="Average", period=Duration.minutes(5))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Groundedness Score",
                left=[cloudwatch.Metric(namespace=ns, metric_name="GroundednessScore",
                      statistic="Average", period=Duration.minutes(5))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Model Cost (USD)",
                left=[cloudwatch.Metric(namespace=ns, metric_name="ModelCostUSD",
                      statistic="Sum", period=Duration.hours(1))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Flagged Answers",
                left=[cloudwatch.Metric(namespace=ns, metric_name="FlaggedAnswers",
                      statistic="Sum", period=Duration.minutes(5))], width=8,
            ),
            cloudwatch.GraphWidget(
                title="Scoring DLQ Depth",
                left=[cloudwatch.Metric(
                    namespace="AWS/SQS",
                    metric_name="ApproximateNumberOfMessagesVisible",
                    dimensions_map={"QueueName": dlq.queue_name},
                    statistic="Maximum", period=Duration.minutes(5),
                )], width=8,
            ),
        )

    def _make_alarms(self, topic: sns.Topic, dlq: sqs.Queue) -> None:
        """Create CloudWatch alarms wired to the SNS alert topic."""
        ns = _CW_NAMESPACE

        alarm_specs = [
            ("HallucinationAlarm", "ai-obs-high-hallucination", ns,
             "HallucinationScore", 0.5, 2, "Average",
             "Average hallucination > 0.5 over two 5-min windows"),
            ("ErrorRateAlarm", "ai-obs-high-error-rate", ns,
             "ErrorRate", 0.05, 3, "Average",
             "Error rate > 5% over three 5-min windows"),
            ("FlagAlarm", "ai-obs-flag-spike", ns,
             "FlaggedAnswers", 10, 1, "Sum",
             "More than 10 flagged answers in a single 5-min window"),
        ]

        for alarm_id, name, namespace, metric_name, threshold, periods, stat, desc in alarm_specs:
            alarm = cloudwatch.Alarm(
                self, alarm_id,
                alarm_name=name,
                alarm_description=desc,
                metric=cloudwatch.Metric(
                    namespace=namespace, metric_name=metric_name,
                    statistic=stat, period=Duration.minutes(5),
                ),
                threshold=threshold,
                evaluation_periods=periods,
                comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            alarm.add_alarm_action(cw_actions.SnsAction(topic))

        dlq_alarm = cloudwatch.Alarm(
            self, "DLQAlarm",
            alarm_name="ai-obs-dlq-messages",
            alarm_description="Messages in scoring DLQ: investigate poison spans",
            metric=cloudwatch.Metric(
                namespace="AWS/SQS",
                metric_name="ApproximateNumberOfMessagesVisible",
                dimensions_map={"QueueName": dlq.queue_name},
                statistic="Maximum", period=Duration.minutes(5),
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        dlq_alarm.add_alarm_action(cw_actions.SnsAction(topic))
