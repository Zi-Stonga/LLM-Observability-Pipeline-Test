"""CDK application entry point."""

import aws_cdk as cdk

from cdk_stack.ai_observability_stack import AiObservabilityStack

app = cdk.App()
AiObservabilityStack(
    app,
    "AiObservabilityStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account"),
        region=app.node.try_get_context("region") or "us-east-1",
    ),
)
app.synth()
