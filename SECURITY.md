# Security policy

## Supported versions

Security fixes are provided for the latest release.

## Reporting

Use GitHub's private vulnerability reporting for this repository. If it is not
available, use the private contact route on the maintainer's GitHub profile. Do
not open a public issue with exploit details, webhook secrets, request bodies,
or personal data.

Include the affected version, impact, reproduction steps using synthetic data,
and any suggested mitigation. You should receive an acknowledgement within
seven days.

WebhookWitness accepts loopback targets only and does not require provider
credentials. Treat service and probe logs as local application output: the tool
does not add request data to reports, but your application may log it itself.
