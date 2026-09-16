import os
from datetime import date
from functools import wraps
from io import BytesIO
from flask import Flask, render_template, redirect, url_for, request, flash, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, inspect
from openpyxl import Workbook
from openpyxl.styles import Font

app=Flask(__name__)
app.config['SECRET_KEY']=os.getenv('SECRET_KEY','dev-change-me')
db_url=os.getenv('DATABASE_URL','sqlite:///educontrol.db')
if db_url.startswith('postgres://'): db_url=db_url.replace('postgres://','postgresql://',1)
app.config['SQLALCHEMY_DATABASE_URI']=db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS']=False
db=SQLAlchemy(app)
login_manager=LoginManager(app); login_manager.login_view='login'

class User(UserMixin,db.Model):
    id=db.Column(db.Integer,primary_key=True)
    name=db.Column(db.String(120),nullable=False)
    email=db.Column(db.String(180),unique=True,nullable=False)
    password_hash=db.Column(db.String(255),nullable=False)
    role=db.Column(db.String(30),default='teacher')
    active=db.Column(db.Boolean,default=True,nullable=False)
    def get_id(self): return str(self.id)
    @property
    def is_active(self): return bool(self.active)

class Group(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(80),nullable=False); year=db.Column(db.Integer,default=lambda:date.today().year); teacher_id=db.Column(db.Integer,db.ForeignKey('user.id'))
    teacher=db.relationship('User',foreign_keys=[teacher_id])
class Student(db.Model):
    id=db.Column(db.Integer,primary_key=True); full_name=db.Column(db.String(180),nullable=False); identification=db.Column(db.String(50)); birth_date=db.Column(db.Date); guardian_name=db.Column(db.String(180)); guardian_phone=db.Column(db.String(50)); active=db.Column(db.Boolean,default=True); group_id=db.Column(db.Integer,db.ForeignKey('group.id'),nullable=False); group=db.relationship('Group')
class Subject(db.Model):
    id=db.Column(db.Integer,primary_key=True); name=db.Column(db.String(100),nullable=False); group_id=db.Column(db.Integer,db.ForeignKey('group.id'),nullable=False); group=db.relationship('Group')
class Attendance(db.Model):
    id=db.Column(db.Integer,primary_key=True); student_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False); subject_id=db.Column(db.Integer,db.ForeignKey('subject.id'),nullable=False); day=db.Column(db.Date,default=date.today); status=db.Column(db.String(20),default='P'); student=db.relationship('Student'); subject=db.relationship('Subject')
class Activity(db.Model):
    id=db.Column(db.Integer,primary_key=True); subject_id=db.Column(db.Integer,db.ForeignKey('subject.id'),nullable=False); title=db.Column(db.String(180),nullable=False); component=db.Column(db.String(40),nullable=False); max_points=db.Column(db.Float,default=100); day=db.Column(db.Date,default=date.today); subject=db.relationship('Subject')
class Grade(db.Model):
    id=db.Column(db.Integer,primary_key=True); activity_id=db.Column(db.Integer,db.ForeignKey('activity.id'),nullable=False); student_id=db.Column(db.Integer,db.ForeignKey('student.id'),nullable=False); points=db.Column(db.Float,default=0); activity=db.relationship('Activity'); student=db.relationship('Student')

@login_manager.user_loader
def load_user(uid): return db.session.get(User,int(uid))

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args,**kwargs):
        if current_user.role!='admin': abort(403)
        return fn(*args,**kwargs)
    return wrapper

def visible_groups_query():
    if current_user.role in ('admin','direction'): return Group.query
    return Group.query.filter_by(teacher_id=current_user.id)

def owned_group(gid):
    q=Group.query.filter_by(id=gid)
    if current_user.role not in ('admin','direction'): q=q.filter_by(teacher_id=current_user.id)
    return q.first_or_404()

@app.route('/')
def index(): return redirect(url_for('dashboard')) if current_user.is_authenticated else redirect(url_for('login'))
@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(email=request.form['email'].strip().lower()).first()
        if u and u.active and check_password_hash(u.password_hash,request.form['password']): login_user(u); return redirect(url_for('dashboard'))
        flash('Usuario o contraseña incorrectos, o el usuario está inactivo.','danger')
    return render_template('login.html')
@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('login'))
@app.route('/dashboard')
@login_required
def dashboard():
    groups=visible_groups_query().order_by(Group.year.desc(),Group.name).all(); gids=[g.id for g in groups]
    students=Student.query.filter(Student.group_id.in_(gids),Student.active==True).count() if gids else 0
    teachers=User.query.filter_by(role='teacher',active=True).count() if current_user.role in ('admin','direction') else None
    return render_template('dashboard.html',groups=groups,students=students,teachers=teachers)

@app.route('/teachers',methods=['GET','POST'])
@admin_required
def teachers():
    if request.method=='POST':
        email=request.form['email'].strip().lower()
        if User.query.filter_by(email=email).first(): flash('Ya existe un usuario con ese correo.','danger')
        else:
            db.session.add(User(name=request.form['name'].strip(),email=email,password_hash=generate_password_hash(request.form['password']),role=request.form.get('role','teacher'),active=True)); db.session.commit(); flash('Usuario creado correctamente.','success')
        return redirect(url_for('teachers'))
    rows=User.query.order_by(User.name).all()
    return render_template('teachers.html',teachers=rows)

@app.post('/teachers/<int:uid>/toggle')
@admin_required
def teacher_toggle(uid):
    u=User.query.get_or_404(uid)
    if u.id==current_user.id: flash('No puedes inactivar tu propio usuario.','warning')
    else: u.active=not u.active; db.session.commit(); flash('Estado actualizado.','success')
    return redirect(url_for('teachers'))

@app.route('/teachers/<int:uid>/edit',methods=['GET','POST'])
@admin_required
def teacher_edit(uid):
    u=User.query.get_or_404(uid)
    if request.method=='POST':
        email=request.form['email'].strip().lower(); duplicate=User.query.filter(User.email==email,User.id!=u.id).first()
        if duplicate: flash('Ese correo ya está en uso.','danger')
        else:
            u.name=request.form['name'].strip(); u.email=email; u.role=request.form['role']; db.session.commit(); flash('Usuario actualizado.','success'); return redirect(url_for('teachers'))
    return render_template('teacher_edit.html',teacher=u)

@app.post('/teachers/<int:uid>/password')
@admin_required
def teacher_password(uid):
    u=User.query.get_or_404(uid); pwd=request.form.get('password','')
    if len(pwd)<8: flash('La contraseña debe tener al menos 8 caracteres.','danger')
    else: u.password_hash=generate_password_hash(pwd); db.session.commit(); flash(f'Contraseña de {u.name} actualizada.','success')
    return redirect(url_for('teachers'))

@app.route('/groups',methods=['GET','POST'])
@login_required
def groups():
    teachers=User.query.filter_by(role='teacher',active=True).order_by(User.name).all() if current_user.role=='admin' else []
    if request.method=='POST':
        teacher_id=current_user.id
        if current_user.role=='admin': teacher_id=int(request.form['teacher_id'])
        elif current_user.role=='direction': abort(403)
        db.session.add(Group(name=request.form['name'],year=int(request.form['year']),teacher_id=teacher_id)); db.session.commit(); flash('Grupo creado.','success'); return redirect(url_for('groups'))
    return render_template('groups.html',groups=visible_groups_query().order_by(Group.year.desc(),Group.name).all(),teachers=teachers)

@app.post('/groups/<int:gid>/assign')
@admin_required
def group_assign(gid):
    g=Group.query.get_or_404(gid); uid=int(request.form['teacher_id']); u=User.query.filter_by(id=uid,role='teacher',active=True).first_or_404(); g.teacher_id=u.id; db.session.commit(); flash('Docente asignado al grupo.','success'); return redirect(url_for('groups'))

@app.route('/students',methods=['GET','POST'])
@login_required
def students():
    groups=visible_groups_query().all(); gids=[g.id for g in groups]
    if request.method=='POST':
        if current_user.role=='direction': abort(403)
        gid=int(request.form['group_id']); owned_group(gid)
        db.session.add(Student(full_name=request.form['full_name'],identification=request.form.get('identification'),guardian_name=request.form.get('guardian_name'),guardian_phone=request.form.get('guardian_phone'),group_id=gid)); db.session.commit(); flash('Estudiante registrado.','success'); return redirect(url_for('students'))
    rows=Student.query.filter(Student.group_id.in_(gids)).order_by(Student.full_name).all() if gids else []
    return render_template('students.html',students=rows,groups=groups)
@app.post('/students/<int:sid>/delete')
@login_required
def student_delete(sid):
    if current_user.role=='direction': abort(403)
    s=Student.query.get_or_404(sid); owned_group(s.group_id); s.active=False; db.session.commit(); flash('Estudiante desactivado.','warning'); return redirect(url_for('students'))
@app.route('/subjects',methods=['GET','POST'])
@login_required
def subjects():
    groups=visible_groups_query().all(); gids=[g.id for g in groups]
    if request.method=='POST':
        if current_user.role=='direction': abort(403)
        gid=int(request.form['group_id']); owned_group(gid); db.session.add(Subject(name=request.form['name'],group_id=gid)); db.session.commit(); return redirect(url_for('subjects'))
    rows=Subject.query.filter(Subject.group_id.in_(gids)).all() if gids else []
    return render_template('subjects.html',subjects=rows,groups=groups)
@app.route('/attendance/<int:subject_id>',methods=['GET','POST'])
@login_required
def attendance(subject_id):
    sub=Subject.query.get_or_404(subject_id); owned_group(sub.group_id); students=Student.query.filter_by(group_id=sub.group_id,active=True).order_by(Student.full_name).all(); day=date.fromisoformat(request.values.get('day',date.today().isoformat()))
    if request.method=='POST':
        if current_user.role=='direction': abort(403)
        for s in students:
            a=Attendance.query.filter_by(student_id=s.id,subject_id=sub.id,day=day).first()
            if not a: a=Attendance(student_id=s.id,subject_id=sub.id,day=day); db.session.add(a)
            a.status=request.form.get(f's_{s.id}','P')
        db.session.commit(); flash('Asistencia guardada.','success'); return redirect(url_for('attendance',subject_id=sub.id,day=day.isoformat()))
    existing={a.student_id:a.status for a in Attendance.query.filter_by(subject_id=sub.id,day=day).all()}
    return render_template('attendance.html',subject=sub,students=students,day=day,existing=existing)
@app.route('/activities/<int:subject_id>',methods=['GET','POST'])
@login_required
def activities(subject_id):
    sub=Subject.query.get_or_404(subject_id); owned_group(sub.group_id)
    if request.method=='POST':
        if current_user.role=='direction': abort(403)
        activity_day=date.fromisoformat(request.form.get('day') or date.today().isoformat())
        act=Activity(subject_id=sub.id,title=request.form['title'].strip(),component=request.form['component'],max_points=float(request.form['max_points']),day=activity_day)
        db.session.add(act); db.session.commit(); flash('Evaluación creada. Ya puedes registrar las calificaciones.','success'); return redirect(url_for('grades',activity_id=act.id))
    return render_template('activities.html',subject=sub,activities=Activity.query.filter_by(subject_id=sub.id).order_by(Activity.day.desc()).all(),today=date.today().isoformat())
@app.route('/grades/<int:activity_id>',methods=['GET','POST'])
@login_required
def grades(activity_id):
    act=Activity.query.get_or_404(activity_id); owned_group(act.subject.group_id); students=Student.query.filter_by(group_id=act.subject.group_id,active=True).order_by(Student.full_name).all()
    if request.method=='POST':
        if current_user.role=='direction': abort(403)
        for s in students:
            g=Grade.query.filter_by(activity_id=act.id,student_id=s.id).first()
            if not g: g=Grade(activity_id=act.id,student_id=s.id); db.session.add(g)
            g.points=float(request.form.get(f'g_{s.id}') or 0)
        db.session.commit(); flash('Notas guardadas.','success'); return redirect(url_for('grades',activity_id=act.id))
    existing={g.student_id:g.points for g in Grade.query.filter_by(activity_id=act.id).all()}
    return render_template('grades.html',activity=act,students=students,existing=existing)
@app.route('/reports/grades/<int:subject_id>.xlsx')
@login_required
def grades_excel(subject_id):
    sub=Subject.query.get_or_404(subject_id); owned_group(sub.group_id); students=Student.query.filter_by(group_id=sub.group_id,active=True).order_by(Student.full_name).all(); acts=Activity.query.filter_by(subject_id=sub.id).order_by(Activity.day).all()
    wb=Workbook(); ws=wb.active; ws.title='Calificaciones'; ws.append(['EduControl CR',sub.group.name,sub.name]); ws.append([]); ws.append(['Estudiante']+[a.title for a in acts]+['Promedio'])
    for c in ws[3]: c.font=Font(bold=True)
    for s in students:
        vals=[]
        for a in acts:
            g=Grade.query.filter_by(activity_id=a.id,student_id=s.id).first(); vals.append(round((g.points/a.max_points*100),2) if g and a.max_points else '')
        nums=[v for v in vals if isinstance(v,(int,float))]; ws.append([s.full_name]+vals+[round(sum(nums)/len(nums),2) if nums else ''])
    ws.freeze_panes='B4'; ws.column_dimensions['A'].width=32
    bio=BytesIO(); wb.save(bio); bio.seek(0); return send_file(bio,as_attachment=True,download_name=f'notas_{sub.name}_{sub.group.name}.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

def migrate_schema():
    db.create_all()
    cols={c['name'] for c in inspect(db.engine).get_columns('user')}
    if 'active' not in cols:
        db.session.execute(text('ALTER TABLE "user" ADD COLUMN active BOOLEAN DEFAULT TRUE NOT NULL'))
        db.session.commit()

@app.cli.command('init-db')
def init_db():
    migrate_schema()
    demo=User.query.filter_by(email='docente@demo.cr').first()
    if not demo:
        db.session.add(User(name='Docente Demo',email='docente@demo.cr',password_hash=generate_password_hash('Cambiar123!'),role='teacher',active=True))
    admin=User.query.filter_by(email='admin@educontrol.cr').first()
    if not admin:
        db.session.add(User(name='Administrador',email='admin@educontrol.cr',password_hash=generate_password_hash('Admin123!'),role='admin',active=True))
    db.session.commit(); print('Admin: admin@educontrol.cr / Admin123!')

with app.app_context():
    try: migrate_schema()
    except Exception as e: print('Migración pendiente:',e)
if __name__=='__main__': app.run(debug=True)
