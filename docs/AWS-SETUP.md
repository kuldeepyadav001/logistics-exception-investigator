# AWS Setup Guide (for the account owner)

The project has **no AWS account yet**. Everything below is what the system needs.
Recommended region: **`ap-south-1` (Mumbai)** — closest, all required services available.

## Step 0 — Create the AWS account (do this first, it takes ~15–30 min)

1. https://aws.amazon.com/ → Create account (email, phone, payment card). Complete phone verification.
2. Once in: **enable MFA on the root user** (IAM → Security credentials).
3. Stay in region **ap-south-1** (top-right region picker) for everything below.

## Step 1 — The services this project uses (and why)

| Service | Job in our system | What you must do in the console |
| --- | --- | --- |
| **Amazon S3** | Stores uploaded source documents (PO/BOL/POD/INVOICE PDFs) | Create one bucket: `lei-documents-<anything-unique>` in ap-south-1. **Block all public access ON.** No versioning needed for MVP. |
| **AWS Lambda** | Runs the API + workflow functions (extract, reconcile, investigate) | Nothing to pre-enable — the agent deploys it via CLI. |
| **Amazon API Gateway** | Exposes the Lambda functions as an HTTP API | Nothing to pre-enable — created by the agent via CLI. |
| **Amazon DynamoDB** | Shipment / document / evidence / exception / investigation / decision / audit tables | Nothing to pre-enable — tables created by the agent via CLI (7 small tables, pay-per-request). |
| **Amazon Textract** | Real invoice/receipt document extraction (AnalyzeExpense / AnalyzeDocument) | **Console → Textract → Enable service.** (Free tier: 1,000 pages/month for 12 months.) |
| **Amazon Bedrock** | The AI investigation layer (evidence-grounded summary + recommendation) | **Console → Bedrock → Models → enable a Claude model** (e.g. Claude 3.5 Haiku or Sonnet — cheapest that returns reliable structured JSON). Some models need "Request model access" (usually instant for Claude). |
| **IAM** (account feature) | Least-privilege access for the agent's deployment | Create **one IAM user** (machine access, no console) as described in Step 2. |
| **CloudWatch Logs** (automatic with Lambda) | Observability: every Lambda run logged | Automatic. Free for 90 days per log group. |
| **AWS Amplify Hosting** (or S3 static + CloudFront) | Hosts the React frontend | **Console → Amplify → Hosting → create app** when the agent says "deploy time" (or the agent can do it via CLI). |

**Optional / intentionally skipped for MVP:** Cognito (no auth in the 3-min demo — ADR-004), Step Functions/EventBridge (added only if synchronous flow proves insufficient — ADR-008).

## Step 2 — IAM user for the agent (exact permissions)

1. **IAM → Users → Add user** → name e.g. `lei-hackathon-agent` → **Programmatic access** only.
2. Attach these **managed policies**:
   - `AmazonS3FullAccess` (bucket-scoped would be tighter; full is acceptable for a throwaway hackathon account — tighten before any real use)
   - `DynamoDBFullAccess`
   - `AWSLambdaFullAccess`
   - `AmazonAPIGatewayAdministrator`
   - `AmazonTextractFullAccess`
   - `AmazonBedrockFullAccess`
   - `CloudWatchLogsFullAccess`
   - `IAMPassRole` is NOT needed — instead the agent will create the Lambda execution role itself, so add: `IAMCreateRole`/`IAMPassRole` via an inline policy if role creation is denied; the agent will tell you if a specific IAM error appears.
3. **Generate an access key** for that user. Send the **Access Key ID + Secret Access Key** to the agent via env vars / chat — **never commit them anywhere**. The agent puts them in `.env` (gitignored) and uses the AWS CLI.
4. Cost guard: **Billing → Budgets → create a $10 budget with 100% alert.** The whole event should cost well under $5 on the free tiers above.

## Step 3 — What to read while the account is being created (~30 min, worth it)

- S3 buckets & ACLs basics: https://docs.aws.amazon.com/AmazonS3/latest/userguide/GetStartedWithS3.html
- DynamoDB data model (tables, keys): https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.html
- Textract AnalyzeExpense API (our invoice extraction call): https://docs.aws.amazon.com/textract/latest/APIReference/API_AnalyzeExpense.html
- Textract invoices/receipts guide: https://docs.aws.amazon.com/textract/latest/dg/invoices-receipts.html
- AWS reference: receipt/invoice processing pipeline with Textract: https://aws.amazon.com/blogs/machine-learning/build-a-receipt-and-invoice-processing-pipeline-with-amazon-textract/
- Lambda + API Gateway intro: https://docs.aws.amazon.com/lambda/latest/dg/getting-started.html
- Bedrock invoke model (structured output): https://docs.aws.amazon.com/bedrock/latest/userguide/models-invoking.html

## Step 4 — Signal to the agent

When ready, send: **region + Access Key ID + Secret** (and confirm Textract + one Bedrock Claude model are enabled). The agent then: installs AWS CLI, provisions S3 bucket (or uses yours), DynamoDB tables, Lambda + API Gateway, Amplify app, runs the full pipeline on AWS, re-runs the evaluation, and the demo shows genuine AWS processing.

**Security note:** these credentials live only in the sandbox `.env` (gitignored), are never committed, and can be rotated/deleted in IAM at any time.
