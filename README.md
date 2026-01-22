# Container Registry - Mythic C2 3rd Party Service Payload

A Mythic C2 integration that wraps the `skopeo` binary to interact with OCI container registries through Mythic's web UI. This service payload allows red team operators to perform container registry operations directly from Mythic.

## Overview

This payload type is a **service payload** (similar to the BloodHound payload) that creates a callback in Mythic for interacting with container registries. It wraps the `skopeo` binary to provide functionality similar to what skopeo offers on the command line, but integrated into Mythic's web interface.

## Features

- Inspect container images
- Copy images between registries
- Delete images from registries
- List all repositories in a registry (catalog)
- List tags for repositories
- Sync images between registries or to local storage
- Support for authenticated and insecure registry connections
- Integrated into Mythic's web UI

## Installation

### Using mythic-cli

```bash
# From your Mythic installation directory
./mythic-cli install github https://github.com/elreydetoda/container_registry
```

### Manual Installation

1. Clone this repository into your Mythic `InstalledServices` directory:

```bash
cd /opt/Mythic/InstalledServices
git clone https://github.com/elreydetoda/container_registry
```

2. Start the container:

```bash
./mythic-cli payload start container_registry
```

## Prerequisites

- Mythic C2 Framework installed
- Docker (for containerized deployment)
- Skopeo binary (included in the Docker container)

## Usage

### Creating a Payload

1. Navigate to the Mythic web UI
2. Go to "Create Components" > "Create Payload"
3. Select "container_registry" as the payload type
4. Configure the build parameters:
   - **registry_url**: Default container registry URL (e.g., docker.io, ghcr.io, quay.io)
   - **registry_username**: Optional default username for registry authentication
   - **registry_password**: Optional default password/token for registry authentication
   - **insecure**: Allow insecure (HTTP) registry connections

5. Create the payload - this will establish a callback in Mythic

### Available Commands

#### inspect

Inspect a container image in a registry.

**Parameters:**
- `image`: Image to inspect (e.g., `docker://docker.io/library/alpine:latest`)
- `username`: Registry username (optional, overrides build parameter)
- `password`: Registry password/token (optional, overrides build parameter)
- `insecure`: Allow insecure connections (optional)
- `raw`: Return raw manifest instead of formatted output (optional)

**Example:**
```json
{
  "image": "docker://docker.io/library/alpine:latest"
}
```

#### copy

Copy a container image between registries.

**Parameters:**
- `source`: Source image (e.g., `docker://docker.io/library/alpine:latest`)
- `destination`: Destination image (e.g., `docker://myregistry.com/alpine:latest`)
- `src_username`: Source registry username (optional)
- `src_password`: Source registry password/token (optional)
- `dest_username`: Destination registry username (optional)
- `dest_password`: Destination registry password/token (optional)
- `src_insecure`: Allow insecure source connections (optional)
- `dest_insecure`: Allow insecure destination connections (optional)
- `all`: Copy all images if source is a list (optional)

**Example:**
```json
{
  "source": "docker://docker.io/library/alpine:latest",
  "destination": "docker://myregistry.com/alpine:latest",
  "dest_username": "myuser",
  "dest_password": "mytoken"
}
```

#### delete

Delete a container image from a registry.

**Parameters:**
- `image`: Image to delete (e.g., `docker://docker.io/myrepo/myimage:tag`)
- `username`: Registry username (optional)
- `password`: Registry password/token (optional)
- `insecure`: Allow insecure connections (optional)

**Example:**
```json
{
  "image": "docker://myregistry.com/myrepo/myimage:tag",
  "username": "myuser",
  "password": "mytoken"
}
```

#### list_catalog

List all repositories in a registry using the Docker Registry HTTP API V2.

**Parameters:**
- `registry_url`: Registry URL (e.g., `https://registry-1.docker.io`, `https://ghcr.io`)
- `username`: Registry username (optional)
- `password`: Registry password/token (optional)
- `insecure`: Allow insecure connections (skip TLS verification) (optional)

**Example:**
```json
{
  "registry_url": "https://myregistry.com",
  "username": "myuser",
  "password": "mytoken"
}
```

#### list_tags

List all tags for a repository.

**Parameters:**
- `repository`: Repository to list tags for (e.g., `docker://docker.io/library/alpine`)
- `username`: Registry username (optional)
- `password`: Registry password/token (optional)
- `insecure`: Allow insecure connections (optional)

**Example:**
```json
{
  "repository": "docker://docker.io/library/alpine"
}
```

#### sync

Synchronize images between registries or to local storage.

**Parameters:**
- `source`: Source transport (e.g., `docker://registry.example.com/myimage`)
- `destination`: Destination transport (e.g., `dir:/path/to/dir`)
- `src_username`: Source registry username (optional)
- `src_password`: Source registry password/token (optional)
- `dest_username`: Destination registry username (optional)
- `dest_password`: Destination registry password/token (optional)
- `src_insecure`: Allow insecure source connections (optional)
- `dest_insecure`: Allow insecure destination connections (optional)

**Example:**
```json
{
  "source": "registry.example.com/myimage",
  "destination": "/tmp/myimage",
  "src_username": "myuser",
  "src_password": "mytoken"
}
```

## Architecture

This payload follows the Mythic 3rd party service payload pattern:

```
container_registry/
├── Payload_Type/
│   └── container_registry/
│       ├── container_registry/
│       │   ├── agent_functions/
│       │   │   ├── __init__.py
│       │   │   ├── builder.py       # Payload type definition
│       │   │   ├── inspect.py       # Inspect command
│       │   │   ├── copy.py          # Copy command
│       │   │   ├── delete.py        # Delete command
│       │   │   ├── list_catalog.py  # List catalog command
│       │   │   ├── list_tags.py     # List tags command
│       │   │   └── sync.py          # Sync command
│       │   └── __init__.py
│       ├── main.py                  # Entry point
│       └── Dockerfile               # Container definition
├── config.json                      # Mythic configuration
└── README.md                        # This file
```

## References

- [Mythic Documentation](https://docs.mythic-c2.net/)
- [Skopeo Documentation](https://github.com/containers/skopeo)
- [BloodHound Mythic Integration](https://github.com/MythicAgents/bloodhound/)
- [Container Wrapper Example](https://github.com/elreydetoda/container_wrapper)

## Author

@elreydetoda

## License

MIT License - See LICENSE file for details
