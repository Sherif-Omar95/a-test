# shellcheck shell=bash
# Shared settings for the helper scripts. Override with environment variables.
STACK="${STACK:-scalable-web}"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"

output() {
  aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
