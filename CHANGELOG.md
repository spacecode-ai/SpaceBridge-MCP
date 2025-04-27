# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2025-04-24

### Changed
- Refined SpaceBridge tool descriptions to mandate `project_name` and clarify usage. (Fixes 35#12)
- Corrected the `search_issues` client parameter from `type` to `search_type`. (Fixes 35#12)
- Updated commit message guidelines in `.roo/rules/01-general.md`. (Fixes 35#12)
- Added `dist/` directory to `.gitignore`. (Fixes 35#12)

## [0.2.2] - 2025-04-22

### Changed
- Set default `search_type` to `similarity` for the `search_issues` tool.

## [0.2.1] - 2025-04-22

### Added
- Add CHANGELOG.md to track changes.

### Fixed
- Default to https://spacebridge.io for SpaceBridge API URL if not set via environment or arguments.
- Require `SPACEBRIDGE_API_KEY` and `OPENAI_API_KEY` for server startup.

## [0.2.0] - 2025-04-21

### Added
- Initial release of the SpaceBridge MCP server.
- Basic server setup with tool registration.
- SpaceBridge client implementation for interacting with the SpaceBridge API.
- Tools for searching, getting, creating, and updating issues.
- Unit tests for server and client components.
- Dockerfile for containerization.
- CI/CD configuration using GitLab CI.
- Project documentation (README, PLAN, ROADMAP).
