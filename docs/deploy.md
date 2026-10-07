# Deploying the public demo

The public demo runs on AWS in `us-east-1` (account 026090556175) and is reachable at
`http://54.164.194.68/demo` and `http://54.164.194.68/reset`.

## How it is deployed

| Piece | Value |
|---|---|
| ECS cluster / service | `synannopower2` / `synannopower2` (1 task, EC2 capacity from an Auto Scaling group) |
| Instance | `i-0eaece616a6cf8312` (c6g.4xlarge, Graviton/arm64) |
| Address | Elastic IP `54.164.194.68` (`eipalloc-026481cb1c50be6e9`) associated with the instance |
| Image | `026090556175.dkr.ecr.us-east-1.amazonaws.com/synanno/uwsgi:<git sha>` (also tagged `latest`) |
| Task definition | `synannopower2:5`: container `synanno-uwsgi`, network mode `host`, ports 80 (Flask/uWSGI) and 9015 (Neuroglancer) |
| Environment | `PUBLIC_DNS_SYNANNO=54.164.194.68`, `SYNANNO_PUBLIC_DEMO=1` |
| Logs | CloudWatch log group `/ecs/synannopower2` |

`PUBLIC_DNS_SYNANNO` must be the public address, because the embedded Neuroglancer
view is loaded from `http://<PUBLIC_DNS_SYNANNO>:9015/v/<token>/`.
`SYNANNO_PUBLIC_DEMO=1` limits the app to the bundled H01 data and disables
credential uploads. `SECRET_KEY` is not set: the app generates one at startup.

The demo keeps one shared state for all visitors, and `/reset` and `/demo` wipe it.
That is intended: the demo is a single-user test deployment.

### Release a new version

Pass `--region us-east-1` on every command: the CLI's default region is
`eu-north-1`.

```bash
REPO=026090556175.dkr.ecr.us-east-1.amazonaws.com/synanno/uwsgi
SHA=$(git rev-parse --short HEAD)
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "${REPO%%/*}"
docker build --platform linux/arm64 -f Dockerfile_uwsgi -t "$REPO:$SHA" .
docker push "$REPO:$SHA"
```

Dependencies are pinned in `requirements.lock`. Change a pin there, not in `setup.py`,
when the image needs a different version.

Register a new task definition revision that differs from the current one only in the
image tag, then switch the service. Host networking with fixed ports cannot run two
copies on one instance, so the deployment stops the old task before starting the new
one (minimum healthy 0%, maximum 100%), which means a short downtime:

Availability Zone rebalancing is disabled on the service, because it requires a
maximum above 100% (it was enabled, with minimum 0% / maximum 200%, before October
2026). The deployment circuit breaker with automatic rollback is still on.

```bash
aws ecs update-service --region us-east-1 --cluster synannopower2 \
  --service synannopower2 --task-definition synannopower2:<new revision> \
  --deployment-configuration minimumHealthyPercent=0,maximumPercent=100 \
  --force-new-deployment
aws ecs wait services-stable --region us-east-1 --cluster synannopower2 \
  --services synannopower2
scripts/smoke_test.sh http://54.164.194.68
```

Once the smoke test passes, point `latest` at the new image as well.

## Roll back

Each earlier image stays in ECR under its git SHA. The image that ran before the
security fixes is tagged `rollback-2026-10` and its task definition is
`synannopower2:4` (which still names the old public address in `PUBLIC_DNS_SYNANNO`;
register a copy with `54.164.194.68` if you need the Neuroglancer view to work).

```bash
aws ecs update-service --region us-east-1 --cluster synannopower2 \
  --service synannopower2 --task-definition synannopower2:<known good revision> \
  --force-new-deployment
aws ecs wait services-stable --region us-east-1 --cluster synannopower2 \
  --services synannopower2
```

## If the Auto Scaling group replaces the instance

A replacement instance gets a new auto-assigned public IP, and the Elastic IP is not
moved to it. The demo is then unreachable at `54.164.194.68` until you re-associate it:

```bash
NEW_ID=$(aws ec2 describe-instances --region us-east-1 \
  --filters Name=tag:aws:autoscaling:groupName,Values=Infra-ECS-Cluster-synannopower2-21a3cfe1-ECSAutoScalingGroup-g4TkBP5jzAi6 \
            Name=instance-state-name,Values=running \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
aws ec2 associate-address --region us-east-1 \
  --allocation-id eipalloc-026481cb1c50be6e9 --instance-id "$NEW_ID"
```

The task definition does not need to change: it names the Elastic IP, not the
instance. Run `scripts/smoke_test.sh http://54.164.194.68` afterwards.

## Shell access (SSH)

Port 22 is closed: the security group `synanno-web-app` (`sg-04b8cdbbac3180074`) only
allows ports 80 and 9015. Nothing in the deployment needs SSH. If you need a shell on
the instance, open port 22 for your own IP only, and close it again afterwards:

```bash
MY_IP=$(curl -s https://checkip.amazonaws.com)
aws ec2 authorize-security-group-ingress --region us-east-1 \
  --group-id sg-04b8cdbbac3180074 --protocol tcp --port 22 --cidr "$MY_IP/32"
ssh -i synanno-us-east-1.pem ec2-user@54.164.194.68
aws ec2 revoke-security-group-ingress --region us-east-1 \
  --group-id sg-04b8cdbbac3180074 --protocol tcp --port 22 --cidr "$MY_IP/32"
```
