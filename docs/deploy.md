# Deploying the public demo

The public demo (linked from the README) runs as a single ECS task on one Graviton
(arm64) EC2 instance in AWS `us-east-1`. The concrete account and resource IDs are kept
out of this public repository; ask a maintainer for them. Placeholders below look like
`<account-id>`.

## How it is deployed

- **Image:** `<account-id>.dkr.ecr.us-east-1.amazonaws.com/synanno/uwsgi:<git sha>`,
  built from `Dockerfile_uwsgi` for `linux/arm64`. Dependencies are pinned in
  `requirements.lock`; change a pin there, not in `setup.py`.
- **Task definition:** one container, network mode `host`, port 80 (Flask/uWSGI) and
  port 9015 (Neuroglancer), with the environment:
  - `PUBLIC_DNS_SYNANNO=<elastic-ip>`: the embedded Neuroglancer view is loaded from
    `http://<PUBLIC_DNS_SYNANNO>:9015/v/<token>/`, so this must be the public address.
  - `SYNANNO_PUBLIC_DEMO=1`: limits the app to the bundled H01 data and refuses
    credential uploads.
  - `SECRET_KEY` is not set; the app generates one at startup.
- **Address:** an Elastic IP associated with the instance.
- **Firewall:** the instance's security group allows only ports 80 and 9015.
- **Logs:** CloudWatch, in the service's log group.

The demo keeps one shared state for all visitors, and `/reset` and `/demo` wipe it.
That is intended: the demo is a single-user test deployment.

## Release a new version

Pass `--region us-east-1` on every AWS command.

```bash
REPO=<account-id>.dkr.ecr.us-east-1.amazonaws.com/synanno/uwsgi
SHA=$(git rev-parse --short HEAD)
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "${REPO%%/*}"
docker build --platform linux/arm64 -f Dockerfile_uwsgi -t "$REPO:$SHA" .
docker push "$REPO:$SHA"
```

Register a new task definition revision that differs from the current one only in the
image tag, then switch the service. Host networking with fixed ports cannot run two
copies on one instance, so the service stops the old task before starting the new one
(minimum healthy 0%, maximum 100%; Availability Zone rebalancing is disabled because
it requires a maximum above 100%). Expect a short downtime.

```bash
aws ecs update-service --region us-east-1 --cluster <cluster> --service <service> \
  --task-definition <family>:<new revision> --force-new-deployment
aws ecs wait services-stable --region us-east-1 --cluster <cluster> --services <service>
scripts/smoke_test.sh http://<elastic-ip>
```

Once the smoke test passes, point the `latest` tag at the new image as well.

## Roll back

Switch the service back to an earlier task definition revision with the same
`update-service` command, then run the smoke test. Rollback revisions should reference
their image **by digest** (`…/synanno/uwsgi@sha256:…`), not by a tag such as `latest`,
which moves with every release.

## If the Auto Scaling group replaces the instance

A replacement instance gets a new auto-assigned public IP, and the Elastic IP is not
moved to it. Re-associate it, then run the smoke test:

```bash
NEW_ID=$(aws ec2 describe-instances --region us-east-1 \
  --filters Name=tag:aws:autoscaling:groupName,Values=<asg-name> \
            Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ec2 associate-address --region us-east-1 \
  --allocation-id <eip-allocation-id> --instance-id "$NEW_ID"
```

The task definition does not need to change: it names the Elastic IP, not the instance.

## Shell access (SSH)

Port 22 is closed, and nothing in the deployment needs it. If you need a shell on the
instance, open port 22 for your own IP only, and close it again afterwards:

```bash
MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress --region us-east-1 \
  --group-id <security-group-id> --protocol tcp --port 22 --cidr "$MY_IP/32"
ssh -i <key-file> ec2-user@<elastic-ip>
aws ec2 revoke-security-group-ingress --region us-east-1 \
  --group-id <security-group-id> --protocol tcp --port 22 --cidr "$MY_IP/32"
```
