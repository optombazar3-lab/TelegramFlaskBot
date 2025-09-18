# Overview

This is a Telegram bot built with python-telegram-bot v20+ and Flask, designed for deployment on Render.com. The bot's primary function is subscription verification - users must subscribe to a designated channel before accessing the bot's features. It provides utility commands for retrieving user, chat, and channel IDs, with all interactions in Uzbek language. The bot includes a Flask web server to maintain continuous operation on cloud platforms.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Bot Framework
- **Technology**: python-telegram-bot v20+ with asyncio support
- **Rationale**: Modern Telegram bot library with async capabilities for better performance
- **Architecture Pattern**: Handler-based command processing with callback query support

## Web Server Integration
- **Technology**: Flask web server running alongside the Telegram bot
- **Purpose**: Maintains bot availability on cloud platforms like Render.com that require HTTP endpoints
- **Implementation**: Threaded execution to run both Flask and Telegram bot concurrently

## Subscription Management
- **Verification Method**: Uses `bot.get_chat_member(chat_id, user_id)` API calls
- **Access Control**: All bot features require channel subscription verification
- **User Experience**: Inline keyboard buttons for subscription and verification actions

## Configuration Management
- **Environment Variables**: BOT_TOKEN, CHANNEL_ID, CHANNEL_URL, WARNING_IMAGE_URL
- **Loading**: python-dotenv for environment variable management
- **Security**: Sensitive tokens stored outside codebase

## Command Structure
- **Administrative Commands**: `/start`, `/check_subscription`
- **Utility Commands**: `/user_id`, `/chat_id`, `/channel_id`
- **Interaction Pattern**: Callback query handlers for button interactions

## State Management
- **User Tracking**: Simple in-memory counter (production would use database)
- **Session Handling**: Stateless design with real-time subscription checks

## Logging and Monitoring
- **Logging Level**: INFO level with suppressed verbose loggers to prevent token exposure
- **Error Handling**: Comprehensive exception handling for bot operations

# External Dependencies

## Telegram Bot API
- **Service**: Official Telegram Bot API
- **Authentication**: Bot token from BotFather
- **Operations**: Message sending, callback handling, chat member verification

## Channel Integration
- **Target Channel**: Configurable via CHANNEL_ID environment variable
- **Public Access**: Channel URL for subscription redirects
- **Verification**: Real-time membership status checking

## Deployment Platform
- **Target**: Render.com web service
- **Requirements**: Continuous HTTP service availability
- **Health Check**: Flask endpoint responding to GET requests

## Python Dependencies
- **python-telegram-bot**: Version 20.6 for Telegram API interactions
- **python-dotenv**: Environment variable management
- **flask**: Web server framework for deployment compatibility

## Asset Management
- **Warning Images**: External URLs for subscription warning displays
- **Static Content**: Configurable image URLs via environment variables