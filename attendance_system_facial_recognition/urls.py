from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from recognition import views as recog_views
from users import views as users_views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', recog_views.home, name='home'),
    path('dashboard/', recog_views.dashboard, name='dashboard'),

    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', users_views.register, name='register'),

    path('add_photos/', recog_views.add_photos, name='add-photos'),
    path('train/', recog_views.train, name='train'),

    path('mark_attendance_in/', recog_views.mark_attendance_in, name='mark-attendance-in'),
    path('mark_attendance_out/', recog_views.mark_attendance_out, name='mark-attendance-out'),

    path('view_attendance/', recog_views.view_attendance_home, name='view-attendance-home'),
    path('view_attendance/date/', recog_views.view_attendance_date, name='view-attendance-date'),
    path('view_attendance/employee/', recog_views.view_attendance_employee, name='view-attendance-employee'),
    path('view_my_attendance/', recog_views.view_my_attendance, name='view-my-attendance'),

    path('not_authorised/', recog_views.not_authorised, name='not-authorised'),
    path('export_csv/', recog_views.export_csv, name='export-csv'),

    path('api/recognize/', recog_views.api_recognize, name='api-recognize'),
    path('api/capture_photo/', recog_views.api_capture_photo, name='api-capture-photo'),
    path('api/mark_attendance/', recog_views.api_mark_attendance, name='api-mark-attendance'),
    path('api/model_status/', recog_views.api_model_status, name='api-model-status'),
]
