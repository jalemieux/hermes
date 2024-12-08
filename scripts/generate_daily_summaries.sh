#!/bin/bash

# Activate virtual environment if using one
# source /path/to/venv/bin/activate

# Set environment variables if needed
# export FLASK_ENV=production

# Navigate to project directory
cd /path/to/project

# Run the task
python -m app.tasks daily_summaries

# Log completion
echo "$(date): Daily summary generation completed" >> /var/log/hermes/daily_summaries.log 