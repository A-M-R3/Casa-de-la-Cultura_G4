from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('buscador/', views.buscador_catalogo, name='buscador'),
    path('logout/', views.logout_view, name='logout'),
    path('registro/', views.registro_view, name='registro'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('api/ia/', views.resumen_ia_view, name='resumen_ia'),
    path('valorar/<int:book_id>/', views.valorar_libro, name='valorar_libro'),
    path('dashboard/', views.dashboard_analitico, name='dashboard_analitico'),
    path('mi-biblioteca/', views.mi_biblioteca_view, name='mi_biblioteca'),
    path('eliminar-valoracion/<int:rating_id>/', views.eliminar_valoracion_view, name='eliminar_valoracion'),
]