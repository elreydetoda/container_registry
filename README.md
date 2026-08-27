# Container Registry - Mythic C2 3rd Party Service Payload

A Mythic C2 integration that wraps the `skopeo` binary to interact with OCI container registries through Mythic's web UI. This service payload allows red team operators to perform container registry operations directly from Mythic, with special support for uploading [container_wrapper](https://github.com/elreydetoda/container_wrapper) payloads to registries.

## Overview

This payload type is a **service payload** (similar to the BloodHound payload) that creates a callback in Mythic for interacting with container registries. It wraps the `skopeo` binary to provide functionality similar to what skopeo offers on the command line, but integrated into Mythic's web interface.

## Features

- **Upload container_wrapper payloads** to registries via copy command
- **Inspect container images** to view metadata and manifests
- **Delete images** from registries
- **List all repositories** in a registry using Docker Registry HTTP API V2
- **List tags** for repositories
- Support for authenticated and insecure registry connections
- Atomic credential fallback: use a complete command pair or a complete build pair
- Docker Hub authentication with Docker IDs and personal access tokens (PATs)
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
- [container_wrapper](https://github.com/elreydetoda/container_wrapper) payload type (for upload functionality)

## Usage

### Creating a Payload

1. Navigate to the Mythic web UI
2. Go to "Create Components" > "Create Payload"
3. Select "container_registry" as the payload type
4. Configure the build parameters:
   - **BASE_HOST**: Default container registry URL (e.g., `localhost:5000`, `docker.io`, `ghcr.io`, `quay.io`)
   - **USERNAME**: Optional default username for registry authentication
   - **PASSWORD**: Optional default password/token for registry authentication
   - **INSECURE**: Allow insecure (HTTP) registry connections

5. Create the payload - this will establish a callback in Mythic

### Docker Hub setup

Create a dedicated `container_registry` payload/callback for Docker Hub with these exact build settings:

```text
BASE_HOST=docker.io
USERNAME=<your Docker Hub username>
PASSWORD=<your Docker Hub PAT>
INSECURE=false
```

Use the PAT as the password; do not use the Docker Hub account password. To copy the wrapper image used by this project's QA into the public test repository, set the command destination to:

```text
<username>/testing:<tag>
```

Registry hosts are callback-scoped. Create another callback for another registry instead of supplying a command-level host override.

### Available Commands

#### copy

Upload a container_wrapper payload to the configured registry. This command is specifically designed to work with container images created by the [container_wrapper](https://github.com/elreydetoda/container_wrapper) payload type.

**Parameters:**
- `source` (Payload): Select from available container_wrapper payloads via dynamic dropdown
- `destination_name`: Destination image name with tag (e.g., `alpine:latest`, `myapp:v1.0`)
- `DEST_USERNAME`: Destination registry username (optional; supply together with `DEST_PASSWORD`)
- `DEST_PASSWORD`: Destination registry password/token (optional; supply together with `DEST_USERNAME`)
- `DEST_INSECURE`: Allow insecure destination connections (optional)

**Example:**
```json
{
  "source": "mycontainer.tar - My wrapped payload",
  "destination_name": "malware/backdoor:latest",
  "DEST_USERNAME": "myuser",
  "DEST_PASSWORD": "mytoken"
}
```

**Note:** The source payload is automatically retrieved from Mythic's payload store as an OCI archive and uploaded to the registry using `skopeo copy`.

When both command credentials are empty, `copy` uses the complete build credential pair. Supplying only one command credential is rejected; command and build values are never mixed.

#### inspect

Inspect a container image in the configured registry.

**Parameters:**
- `image_name`: Image name with tag (e.g., `alpine:latest`, `library/alpine:3.18`)
- `USERNAME`: Registry username (optional, falls back to build parameter)
- `PASSWORD`: Registry password/token (optional, falls back to build parameter)
- `INSECURE`: Allow insecure connections (optional, falls back to build parameter)
- `raw`: Return raw manifest instead of formatted output (optional)

**Example:**
```json
{
  "image_name": "alpine:latest"
}
```

**Note:** The full registry URL is constructed automatically using the `BASE_HOST` build parameter, so you only need to provide the image name.

#### delete

Delete a container image from the configured registry.

**Parameters:**
- `image_name`: Image name with tag (e.g., `myrepo/myimage:tag`)
- `USERNAME`: Registry username (optional, falls back to build parameter)
- `PASSWORD`: Registry password/token (optional, falls back to build parameter)
- `INSECURE`: Allow insecure connections (optional, falls back to build parameter)

**Example:**
```json
{
  "image_name": "malware/backdoor:latest"
}
```

#### list_catalog

List all repositories in a registry using the Docker Registry HTTP API V2 `/v2/_catalog` endpoint.

**Parameters:**
- `BASE_HOST`: Registry URL (optional, falls back to build parameter - e.g., `registry-1.docker.io`, `ghcr.io`, `localhost:5000`)
- `USERNAME`: Registry username (optional, falls back to build parameter)
- `PASSWORD`: Registry password/token (optional, falls back to build parameter)
- `INSECURE`: Allow insecure connections/skip TLS verification (optional, falls back to build parameter)

**Example:**
```json
{
  "BASE_HOST": "myregistry.com:5000",
  "USERNAME": "myuser",
  "PASSWORD": "mytoken"
}
```

**Note:** This command uses Python's `requests` library to call only the standard `/v2/_catalog` Registry HTTP API V2 endpoint. Vendor-specific catalog APIs are intentionally out of scope. Hosted registries, including Docker Hub, that do not expose this endpoint will likely reject the request.

#### list_tags

List all tags for a repository in the configured registry.

**Parameters:**
- `image_name`: Repository image name (e.g., `alpine`, `library/alpine`, `myrepo/myimage`)
- `USERNAME`: Registry username (optional, falls back to build parameter)
- `PASSWORD`: Registry password/token (optional, falls back to build parameter)
- `INSECURE`: Allow insecure connections (optional, falls back to build parameter)

**Example:**
```json
{
  "image_name": "alpine"
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
│       │   │   ├── __init__.py          # Auto-loader for commands
│       │   │   ├── builder.py           # Payload type definition
│       │   │   ├── shared.py            # Shared helper functions
│       │   │   ├── copy.py              # Upload container_wrapper payloads
│       │   │   ├── inspect.py           # Inspect images
│       │   │   ├── delete.py            # Delete images
│       │   │   ├── list_catalog.py      # List all repositories
│       │   │   └── list_tags.py         # List tags for repository
│       │   └── __init__.py
│       ├── main.py                      # Entry point
│       └── Dockerfile                   # Container definition
├── config.json                          # Mythic configuration
└── README.md                            # This file
```

### Shared Helper Functions

The `shared.py` module provides common utilities:
- `get_arg_or_build_value()`: Retrieves parameter values with automatic fallback to build parameters
- `normalize_registry_host()`: Removes surrounding whitespace, schemes, and trailing slashes; canonicalizes Docker Hub aliases to `docker.io`
- `resolve_credentials()`: Selects one complete command or build credential pair without mixing sources
- `get_registry_base_url()`: Constructs normalized HTTP/HTTPS registry URLs
- `get_registry_proto_url()`: Constructs normalized `docker://` URLs for skopeo

### Command Parameter Fallback

Credential fallback is atomic. When both command username and password/token are supplied, that pair overrides the build credentials. When both command values are empty, the complete build pair is used. A partial pair at either source is rejected, and a command username is never combined with a build password (or vice versa).

## Development History

Based on git commit history:

1. **Initial code generation** - Claude AI generated the base integration
2. **Added list_catalog function** - Direct HTTP API access to registry catalog
3. **Manual modifications for simplified access** - Added shared helper functions and parameter fallback logic
4. **Adapted copy function** - Modified to upload container_wrapper payloads from Mythic's payload store
5. **Refactoring** - Standardized all commands to use consistent patterns and shared utilities
6. **Removed sync command** - Moved to disabled_cmds until further QA

## References

- [Mythic Documentation](https://docs.mythic-c2.net/)
- [Skopeo Documentation](https://github.com/containers/skopeo)
- [BloodHound Mythic Integration](https://github.com/MythicAgents/bloodhound/) - Reference for service payload pattern
- [Container Wrapper](https://github.com/elreydetoda/container_wrapper) - Creates OCI images from payloads
- [Docker Registry HTTP API V2](https://distribution.github.io/distribution/spec/api/) - Registry API specification

## Author

@elreydetoda

## License

MIT License - See LICENSE file for details
