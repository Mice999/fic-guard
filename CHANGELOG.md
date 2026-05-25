# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- GitHub Actions `release.yml`: push a `v*` tag → auto-build on ubuntu/windows/macos → upload to GitHub Releases
- `fic_guard_entry.py`: PyInstaller entry point (not a user-facing file)
- README: "下载预编译版" section for users who don't have Python installed

### Changed
- `cli.py`: `sys.stdout.reconfigure(encoding='utf-8')` on startup to fix Chinese output on Windows GBK consoles

---

## [0.1.0] - 2026-05-25

### Added
- `fingerprint make / show / watermark / extract / strip`
- `timestamp make / verify`
- `monitor` (offline URL generation + optional DuckDuckGo HTML)
- `safe-publish` interactive checklist
- `guide` quickstart command
