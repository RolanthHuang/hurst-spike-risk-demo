# Security and data handling

This repository is a synthetic demonstration. Do not open an issue containing production rows, user identifiers, IP addresses, credentials, internal table names, screenshots, or derived risk labels.

Store private extracts outside the repository (for example, under `data/private/`, which is git-ignored). Normalize and pseudonymize them inside the approved environment before running this code.

If sensitive information is committed, treat it as exposed even after deleting the file from the latest commit: rotate affected credentials, remove the data from Git history, and follow the data owner's incident process.

