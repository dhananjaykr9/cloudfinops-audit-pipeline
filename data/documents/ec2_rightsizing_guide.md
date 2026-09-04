# AWS EC2 Right-Sizing and Idle Resource Guide

## Overview

EC2 instances represent a significant portion of AWS infrastructure costs. Idle and over-provisioned instances are the primary sources of avoidable compute spend.

---

## Idle EC2 Instance Detection

### Definition

An EC2 instance is considered idle when:
- Average CPU utilization is below 5% for 7 or more consecutive days
- Average network I/O is below 10 MB for the same period

### Cost Impact

Idle instances of common types carry the following on-demand monthly costs:

| Instance Type | Monthly On-Demand Cost (us-east-1) |
|---|---|
| t3.medium | ~$30 |
| m5.large | ~$70 |
| r5.2xlarge | ~$380 |
| c5.4xlarge | ~$550 |

### Recommendation

For confirmed idle instances:

1. **Stop the instance** — preserves the EBS volumes and configuration
2. **Evaluate workload** — determine if the instance serves a scheduled or intermittent purpose
3. **Right-size or terminate** — if no scheduled workload exists, terminate and recover associated EBS volumes

### Remediation Commands

Stop the instance:

```bash
aws ec2 stop-instances --instance-ids <instance-id>
```

Terminate the instance (after confirming it is no longer needed):

```bash
aws ec2 terminate-instances --instance-ids <instance-id>
```

### Policy Reference

AWS Well-Architected Framework — Cost Optimization Pillar: Right size services to meet your needs. CloudWatch metrics for CPU utilization and network I/O should be reviewed weekly.

---

## RDS Idle Instance Detection

### Definition

An RDS database instance is considered idle when:
- Average CPU utilization is below 5% for 7 or more consecutive days
- Average network throughput is below 10 MB for the same period
- No active connections are established

### Recommendation

1. Confirm with the application team whether the database is actively used
2. If idle, consider migrating to **RDS Serverless v2** for intermittent workloads
3. If unused, create a final snapshot and delete the instance

### Remediation Commands

Create a final snapshot:

```bash
aws rds create-db-snapshot \
    --db-instance-identifier <db-instance-id> \
    --db-snapshot-identifier <snapshot-id>
```

Delete the RDS instance:

```bash
aws rds delete-db-instance \
    --db-instance-identifier <db-instance-id> \
    --skip-final-snapshot
```

Migrate to Serverless v2 (for intermittent workloads):

```bash
aws rds modify-db-cluster \
    --db-cluster-identifier <cluster-id> \
    --engine-mode provisioned \
    --serverless-v2-scaling-configuration MinCapacity=0.5,MaxCapacity=2
```

### Cost Impact

- Deleting an idle `db.r5.2xlarge` Multi-AZ RDS instance: ~$1,400/month saved
- Migrating to Serverless v2: pay per ACU-hour, scaling to zero when idle

### Policy Reference

AWS Cost Optimization: Databases — Use Amazon CloudWatch to monitor RDS CPU utilization, database connections, and network throughput. Idle instances without active connections for 7+ days should be reviewed for termination or migration.

---

## EC2 Reserved Instance and Savings Plans

### Recommendation

For stable, predictable workloads running continuously:

- **Compute Savings Plans** provide up to 66% savings vs on-demand
- **EC2 Reserved Instances** provide up to 72% savings for 1-year or 3-year commitments

### Eligibility

An instance is a good candidate for Reserved Instance purchase when:
- Running continuously for more than 30 days
- CPU utilization is consistently above 20%
- The instance type is stable and not frequently changed

### Policy Reference

AWS Cost Optimization: Pricing Models — Evaluate Savings Plans and Reserved Instances for steady-state workloads. Combine with right-sizing analysis before committing.
