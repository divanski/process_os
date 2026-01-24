# eushipments_like Fixture Project

This is a **test fixture** simulating a real shipping/logistics application.

**Purpose**: Enable deterministic integration testing of ProcessOS without requiring access to real production codebases.

## Structure

```
eushipments_like/
├── README.md           # This file
├── config/
│   ├── carriers.yaml   # Carrier configuration
│   └── settings.yaml   # Application settings
├── src/
│   ├── controllers/
│   │   └── shipment_controller.py
│   ├── services/
│   │   ├── carrier_service.py
│   │   └── tracking_service.py
│   └── models/
│       └── shipment.py
```

## Simulated Scenario

This fixture represents an e-commerce shipping platform that:

1. Manages shipments across multiple carriers
2. Provides tracking capabilities
3. Generates shipping labels
4. Calculates shipping rates

## Usage in Tests

```python
from pathlib import Path

# Get fixture path
fixture_path = Path(__file__).parent / "demo" / "eushipments_like"

# Use with host adapter for testing
from process_os.hosts import FilesystemHost, HostPolicy

policy = HostPolicy.default()
host = FilesystemHost(fixture_path, policy)

# Read fixture files
content = host.read_file("config/carriers.yaml")
```

## Determinism

All files in this fixture are **deterministic** - no timestamps, no random values, no environment-dependent content.

## License

Part of ProcessOS test suite. See main repository for license.
