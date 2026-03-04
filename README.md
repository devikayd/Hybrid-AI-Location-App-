# Hybrid AI Location Intelligence Web App 🗺️

A web app that gives you safety and location insights for any UK city. It pulls in real-time data from crime reports, events, news, and points of interest, then uses machine learning to score how safe or popular a location is. You can also chat with an AI assistant, get a day trip plan, and see personalised recommendations based on what you've liked before.

This was built as part of my MSc Data Science project.

---

## What it does✨

- Safety and popularity scores for any UK location using XGBoost models trained on crime, POI, news and event data
- Interactive Leaflet map with layers you can toggle — crimes, events, POIs, news
- Journey planner that picks the best stops near you, orders them by distance, and shows walking times between each
- AI chatbot (DeepSeek Chat) that understands questions like "is it safe in Leeds?" or "plan a day trip to Bath"
- Sentiment analysis on local news using VADER (NLTK)
- Personalised recommendations based on what you've liked or saved

---

## Tech Stack🛠️

**Backend**⚙️ — Python, FastAPI, SQLAlchemy, XGBoost, scikit-learn, NLTK, Redis

**Frontend**🎨 — React 18, Vite, Tailwind CSS, React-Leaflet, Zustand, TanStack Query

**LLM**🤖 — DeepSeek Chat via OpenRouter

---

## Data Sources👩🏻‍💻🗂️

| Source                   | What it provides                | Link                                                                        |
| ------------------------ | ------------------------------- | --------------------------------------------------------------------------- |
| UK Police API            | Crime data                      | https://data.police.uk/docs/                                                |
| Ticketmaster             | Local events                    | https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/ |
| OpenStreetMap / Overpass | Points of interest              | https://overpass-api.de/                                                    |
| NewsAPI                  | Local news                      | https://newsapi.org/                                                        |
| OpenRouteService         | Walking routes and travel times | https://openrouteservice.org/dev/#/signup                                   |
| OpenRouter               | LLM access for the chatbot      | https://openrouter.ai/                                                      |
| Nominatim                | Geocoding                       | https://nominatim.org/                                                      |

UK Police, OpenStreetMap, Overpass, and Nominatim are all free with no API key needed. The others need a free account.

---

## Requirements📋

- Python 3.10+
- Node.js 18+
- Redis running locally
- API keys for Ticketmaster, NewsAPI, OpenRouteService, OpenRouter

---

## Setup🚀

### Backend⚙️

```bash
cd backend
python -m venv venv
source venv/bin/activate       # Mac/Linux
venv\Scripts\activate          # Windows

pip install -r requirements.txt

cp .env.example .env
# open .env and fill in your API keys

uvicorn app.main:app --reload
```

### Frontend🎨

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:5173`
API runs at `http://localhost:8000`
API docs at `http://localhost:8000/docs`

---

## Environment Variables🔑

Copy `.env.example` to `.env` inside the `backend/` folder and fill in your keys:

```
DATABASE_URL=sqlite:///./data/dev.db

TICKETMASTER_API_KEY=your_key_here
NEWS_API_KEY=your_key_here
ORS_API_KEY=your_key_here

LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key_here
LLM_MODEL=deepseek/deepseek-chat:free

REDIS_URL=redis://localhost:6379
SECRET_KEY=your_secret_key
DEBUG=True
```

---

## Project Structure📁

```
├── backend/
│   ├── app/
│   │   ├── core/          # config, database, Redis, circuit breakers
│   │   ├── ml/            # feature engineering, XGBoost models, NLP
│   │   ├── models/        # database models
│   │   ├── routers/       # API endpoints
│   │   ├── schemas/       # request/response models
│   │   └── services/      # business logic, external API calls
│   └── requirements.txt
│
└── frontend/
    └── src/
        ├── components/    # UI components
        ├── hooks/         # custom hooks
        ├── services/      # API functions
        └── stores/        # Zustand state
```

---

## Main API Endpoints🔌

| Method | Endpoint                  | Description                               |
| ------ | ------------------------- | ----------------------------------------- |
| GET    | `/api/v1/location-data`   | crimes, events, POIs, news for a location |
| GET    | `/api/v1/scores`          | safety and popularity scores              |
| POST   | `/api/v1/chat`            | send a message to the chatbot             |
| POST   | `/api/v1/trip-plan`       | generate a day trip itinerary             |
| GET    | `/api/v1/summary`         | AI summary for a location                 |
| POST   | `/api/v1/interactions`    | log a like or save                        |
| GET    | `/api/v1/recommendations` | personalised recommendations              |

---

## License

© 2026 Devika Y D. All rights reserved. Built as part of an MSc Data Science dissertation project.
