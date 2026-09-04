# AWS EBS Cost Optimization Guide

## Overview

Amazon Elastic Block Store (EBS) volumes are a common source of unnecessary cloud spend. This guide covers identification and remediation of common EBS cost issues.

---

## gp2 to gp3 Migration

### Issue

The `gp2` volume type uses a burstable IOPS model that ties storage performance directly to volume size. Larger volumes receive more baseline IOPS, which often leads to over-provisioning purely for performance reasons.

### Recommendation

Migrate `gp2` volumes larger than 500 GB to `gp3`.

`gp3` is the current-generation general-purpose SSD volume type. It decouples IOPS and throughput from storage size, allowing independent configuration.

### Cost Impact

- `gp2` price: $0.10 per GB-month
- `gp3` price: $0.08 per GB-month
- Savings: approximately 20% reduction in storage cost
- Additional IOPS on `gp3` are independently configurable at $0.005 per provisioned IOPS-month

### Remediation Command

```bash
aws ec2 modify-volume \
    --volume-id <volume-id> \
    --volume-type gp3
```

### Validation

After modification, verify the volume type has changed:

```bash
aws ec2 describe-volumes \
    --volume-ids <volume-id> \
    --query 'Volumes[*].VolumeType'
```

### Policy Reference

AWS EBS pricing documentation recommends `gp3` as the default volume type for new workloads. Existing `gp2` volumes should be evaluated for migration based on size and IOPS requirements.

---

## Unattached EBS Volumes

### Issue

EBS volumes in the `available` state are not attached to any EC2 instance. These volumes continue to incur charges even when unused.

### Identification

A volume is considered orphaned when:
- State is `available`
- Has been unattached for more than 14 days

### Recommendation

1. Verify the volume is not needed by checking with the resource owner
2. Create a snapshot for archival if data must be retained
3. Delete the unattached volume

### Remediation Commands

Create a snapshot before deletion:

```bash
aws ec2 create-snapshot \
    --volume-id <volume-id> \
    --description "Archive snapshot before deletion"
```

Delete the volume:

```bash
aws ec2 delete-volume --volume-id <volume-id>
```

### Cost Impact

Eliminating unattached volumes saves 100% of the storage cost for that volume. Snapshots cost $0.05 per GB-month, significantly less than active volume pricing.

### Policy Reference

AWS Well-Architected Framework — Cost Optimization Pillar: Manage demand and supply resources. Unused EBS volumes should be identified and removed as part of regular cloud hygiene.

---

## Snapshot Lifecycle Management

### Issue

Outdated EBS snapshots accumulate over time and contribute to storage costs.

### Recommendation

Implement Amazon Data Lifecycle Manager (DLM) to automate snapshot creation and deletion based on retention policies.

```bash
aws dlm create-lifecycle-policy \
    --description "Daily snapshot with 7-day retention" \
    --state ENABLED \
    --execution-role-arn <role-arn> \
    --policy-details file://policy.json
```

### Policy Reference

AWS Cost Optimization: Storage — Implement automated snapshot lifecycle policies to reduce snapshot accumulation costs.
