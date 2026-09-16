# EduControl CR
MVP de gestión docente con Flask/PostgreSQL preparado para Render.

## Incluye
- Login docente y separación básica por docente
- Grupos y año lectivo
- Estudiantes y encargados
- Materias por grupo
- Asistencia por materia y fecha
- Actividades: trabajo cotidiano, tarea, prueba, proyecto u otro
- Registro de notas por estudiante
- Exportación Excel de calificaciones
- Responsive con Bootstrap

## Local
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
flask --app app init-db
flask --app app run
```
Demo: `docente@demo.cr` / `Cambiar123!` (cambiar al desplegar).

## Render
1. Crear PostgreSQL.
2. Crear Web Service desde el repositorio.
3. Build: `pip install -r requirements.txt`
4. Start: `gunicorn app:app`
5. Variables: `DATABASE_URL` y `SECRET_KEY`.
6. Ejecutar una vez `flask --app app init-db` en Shell.

## Próximas fases recomendadas
- CSRF en todos los formularios y formularios WTForms
- CRUD editar/eliminar con auditoría
- Períodos lectivos y componentes/porcentajes configurables por nivel/materia
- Plantillas Excel oficiales/específicas del centro educativo
- Reporte de asistencia Excel/PDF
- Importación masiva Excel
- Observaciones, adecuaciones y comunicaciones (con controles de privacidad)
- Roles admin/dirección/docente
- Multi-centro/multi-tenant
- Backups y bitácora

Nota: los porcentajes de evaluación no están codificados en este MVP; deben configurarse según las reglas vigentes aplicables y el formato que use el centro/MEP.
