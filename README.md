 AI-Based Construction Cost Estimation System

An end-to-end AI-powered system that automates construction cost estimation — from blueprint generation to real-time material price scraping and intelligent cost computation.

 Overview

This project eliminates manual construction cost estimation by integrating:

 AI-driven 2D blueprint generation (SVG)

 Automated material quantity extraction

 Real-time price scraping using Selenium

 Redis-based caching for optimized performance

 Intelligent cost computation with labor & contingency factors

The system provides fast, transparent, and data-driven cost estimates based on live market pricing.

 System Workflow

User Input (Plot Details)
→ Generate 2D SVG Blueprint
→ Extract Materials (Cement, Steel, Sand, Bricks, Aggregates)
→ Scrape Live Prices (IndiaMART + Local Suppliers)
→ Redis Cache (24-hour caching)
→ Cost Calculation (Material + 30% Labor + 12% Contingency)
→ Return Final Cost Estimate

 Tech Stack

Language: Python

Backend: Flask / FastAPI
Frontend: Streamlit
Blueprint Modeling: SVG-based layout logic
Web Scraping: Selenium
Caching: Redis
Data Handling: JSON
Deployment: Local / Cloud

 Project Structure
├── blueprint/
│   └── svg_generator.py
├── scraper/
│   └── price_scraper.py
├── cost_engine/
│   └── calculator.py
├── cache/
│   └── redis_client.py
├── app.py
├── requirements.txt
└── README.md

 Key Features

Automated 2D architectural blueprint generation

Geometry-based material quantity estimation

Live supplier price scraping

Cache-optimized performance

Transparent cost breakdown

Modular & scalable architecture

 Limitations

Blueprint is conceptual (not legally certified)

Prices depend on supplier listing availability

Labor rates are generalized

 Future Enhancements

3D blueprint generation

Region-based labor rate customization

Supplier comparison dashboard

PDF exportable reports

GIS & regulatory integration
