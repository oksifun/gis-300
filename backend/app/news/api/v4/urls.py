from rest_framework.routers import DefaultRouter

from app.news.api.v4.views import NewsCrudViewSet, NewsFilesViewSet, \
    NewsDailyReportViewSet, NewsMarkReadViewSet, NewsUnreadViewSet, \
    NewsHeadImgViewSet

news_router = DefaultRouter()

news_router.register(
    'models/news',
    NewsCrudViewSet,
    basename='news'
)

news_router.register(
    'models/news/head_img',
    NewsHeadImgViewSet,
    basename='head_img'
)

news_router.register(
    'models/news/files',
    NewsFilesViewSet,
    basename='news_files'
)

news_router.register(
    'models/news_daily_report',
    NewsDailyReportViewSet,
    basename='news_daily_report'
)

news_router.register(
    'models/news_mark_read',
    NewsMarkReadViewSet,
    basename='news_daily_report'
)
news_router.register(
    'models/news_unread',
    NewsUnreadViewSet,
    basename='news_unread'
)