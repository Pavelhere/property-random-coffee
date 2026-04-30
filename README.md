# random_coffee_slack

## description
The Random Coffee Bot (RCB) is a weekly virtual networking event that aims to connect members of your Slack community through casual, informal coffee meetings.

Each week, the bot will randomly select two participants and send them a direct message with information on how to make a call for a virtual coffee meeting. These meetings provide an opportunity for participants to get to know each other, exchange ideas, and form new connections.

I hope that this project will help to foster a sense of community among our members and encourage meaningful interactions. I encourage everyone to join in and look forward to having virtual coffee with you!

## tenant matching
The repository now hosts a lightweight tenant-matching service with a minimal web UI and email-first notifications. Tenants sign up through `/join`, admins trigger weekly matches (and download CSV exports) from `/admin/matches`, and proposal responses are handled securely via `/respond`. Legacy Slack behavior survives in `src/legacy_slack_main.py`.

## project status
[![build](https://github.com/kvendingoldo/random_coffee_slack/actions/workflows/pipeline.yml/badge.svg)](https://github.com/kvendingoldo/random_coffee_slack/actions/workflows/pipeline.yml)
