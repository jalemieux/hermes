# Hermes - Your Personal Newsletter Aggregator

Hermes is a modern web application that transforms how you consume newsletter content by aggregating, summarizing, and delivering insights from your subscribed newsletters.

## Why Hermes?

In today's information-rich world, staying on top of multiple newsletters can be overwhelming. Hermes solves this by:

- **Consolidating Content**: Automatically collects and organizes all your newsletter subscriptions in one place
- **Smart Summarization**: Uses AI to generate concise summaries of key points and insights
- **Audio Integration**: Converts summaries into audio format for on-the-go consumption
- **Interactive Insights**: Provides a chatbot interface to dive deeper into specific topics
- **Clean Reading Experience**: Removes ads and promotional content for distraction-free reading

## Key Features

- **Email Integration**: 
  - Dedicated email address for newsletter forwarding
  - Automatic content extraction and organization
  - Support for multiple newsletter sources

- **AI-Powered Summaries**:
  - Daily and weekly digest options
  - Key points extraction
  - Topic-based organization
  - Source attribution

- **Audio Capabilities**:
  - Text-to-speech conversion
  - Audio player with playback controls
  - Mobile-friendly listening experience

- **User Management**:
  - Secure authentication
  - Invitation-based registration
  - Email notifications
  - Reading history tracking

## Technical Stack

- **Backend**: Flask (Python)
- **Database**: SQLAlchemy
- **Frontend**: HTML/CSS with Tailwind CSS
- **AI Integration**: OpenAI GPT-4
- **Email Processing**: MailSlurp
- **Audio Generation**: ElevenLabs
- **Authentication**: Flask-Login
- **OAuth**: Google Login (in progress)

## Development Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the development server:

```bash
python app.py
```

3. Access the application at `http://127.0.0.1:5000`


