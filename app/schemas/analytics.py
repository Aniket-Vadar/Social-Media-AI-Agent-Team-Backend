from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class KpiSummary(BaseModel):
    posts_this_week: int = 4
    scheduled_posts: int = 1
    published_posts: int = 3
    completion_rate_percent: float = 75.0
    engagement_rate: float = 4.8
    impressions: int = 14250
    reach: int = 11200
    follower_growth: int = 320


class TimeSeriesPoint(BaseModel):
    date: str
    impressions: int
    engagement: int
    clicks: int


class AiInsight(BaseModel):
    id: str
    title: str
    summary: str
    recommendations: List[str]
    impact_score: str  # 'high' | 'medium'
    category: str


class AnalyticsDashboardOut(BaseModel):
    kpis: KpiSummary
    timeseries: List[TimeSeriesPoint]
    insights: List[AiInsight]
