# AWS ↔ GCP ↔ Azure Service Mapping

The architect's translation table. Pattern first, vendor second — the same
design lands on any of the three columns.

## Compute

| Need | AWS | GCP | Azure |
| --- | --- | --- | --- |
| Virtual machines | EC2 | Compute Engine | Virtual Machines |
| Managed Kubernetes | EKS | GKE | AKS |
| Serverless functions | Lambda | Cloud Functions / Cloud Run functions | Azure Functions |
| Serverless containers | Fargate / App Runner | Cloud Run | Container Apps |
| PaaS web apps | Elastic Beanstalk | App Engine | App Service |

## Storage & Database

| Need | AWS | GCP | Azure |
| --- | --- | --- | --- |
| Object storage | S3 | Cloud Storage | Blob Storage |
| Block storage | EBS | Persistent Disk | Managed Disks |
| Managed relational | RDS / Aurora | Cloud SQL / AlloyDB | Azure SQL / Database for PostgreSQL |
| Serverless NoSQL | DynamoDB | Firestore / Bigtable | Cosmos DB |
| Caching | ElastiCache | Memorystore | Azure Cache for Redis |
| Data warehouse | Redshift | BigQuery | Synapse / Fabric |

## Networking & Delivery

| Need | AWS | GCP | Azure |
| --- | --- | --- | --- |
| Virtual network | VPC | VPC | VNet |
| Load balancer | ALB / NLB | Cloud Load Balancing | Azure Load Balancer / App Gateway |
| CDN | CloudFront | Cloud CDN | Front Door / Azure CDN |
| DNS | Route 53 | Cloud DNS | Azure DNS |
| Private connectivity | Direct Connect | Cloud Interconnect | ExpressRoute |
| API gateway | API Gateway | Apigee / API Gateway | API Management |

## Messaging & Integration

| Need | AWS | GCP | Azure |
| --- | --- | --- | --- |
| Pub/sub events | SNS / EventBridge | Pub/Sub | Event Grid |
| Queues | SQS | Pub/Sub (pull) / Cloud Tasks | Service Bus / Storage Queues |
| Streaming | Kinesis / MSK | Pub/Sub / Dataflow | Event Hubs |

## Identity, Security, Operations

| Need | AWS | GCP | Azure |
| --- | --- | --- | --- |
| Identity & access | IAM | Cloud IAM | Entra ID + Azure RBAC |
| Secrets | Secrets Manager | Secret Manager | Key Vault |
| Keys/encryption | KMS | Cloud KMS | Key Vault keys |
| Monitoring | CloudWatch | Cloud Monitoring | Azure Monitor |
| Audit log | CloudTrail | Cloud Audit Logs | Activity Log |
| IaC (native) | CloudFormation | Deployment Manager | Bicep / ARM |
| Org structure | Organizations + accounts | Organization + folders + projects | Management groups + subscriptions |

## Reading The Table Honestly

Equivalents are approximate — pricing models, limits, and semantics differ
(DynamoDB ≠ Cosmos DB ≠ Firestore in consistency and pricing). The table tells
you WHERE to look; the current provider docs tell you whether it fits. Services
launch and rename constantly — verify before committing a design.
