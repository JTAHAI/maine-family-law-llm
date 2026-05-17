# Deployment Guide

## Local Development

### API
Run FastAPI locally on port 8000.

### Frontend
Run the React frontend locally on port 3000.

## Security
- Never package vector databases
- Never package uploaded matter files
- Never enable filing-ready export by default

## Release Requirements
- Run evaluation orchestrator
- Verify release manifest
- Verify no runtime state is included
