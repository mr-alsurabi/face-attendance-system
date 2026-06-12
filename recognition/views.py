import os
import json
import base64
import pickle
import datetime
import math
import csv
import io

import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')

from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from .forms import UsernameForm, DateForm, UsernameAndDateForm, DateRangeForm
from users.models import Present, Time


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def is_admin(user):
    return user.is_staff or user.is_superuser


def model_is_trained():
    return settings.SVC_MODEL_PATH.exists() and settings.CLASSES_PATH.exists()


def load_model():
    with open(settings.SVC_MODEL_PATH, 'rb') as f:
        svc = pickle.load(f)
    encoder = LabelEncoder()
    encoder.classes_ = np.load(str(settings.CLASSES_PATH), allow_pickle=True)
    return svc, encoder


def convert_hours_to_str(hours):
    h = int(hours)
    m = math.ceil((hours - h) * 60)
    return f"{h}h {m}m"


def compute_attendance_stats(present_qs, time_qs):
    results = []
    for obj in present_qs:
        date = obj.date
        times_all = time_qs.filter(date=date).order_by('time')
        times_in = times_all.filter(out=False)
        times_out = times_all.filter(out=True)

        time_in = times_in.first().time if times_in.exists() else None
        time_out = times_out.last().time if times_out.exists() else None

        total_hours = 0.0
        if time_in and time_out:
            total_hours = (time_out - time_in).total_seconds() / 3600

        results.append({
            'date': date,
            'present': obj.present,
            'time_in': time_in,
            'time_out': time_out,
            'hours': convert_hours_to_str(total_hours),
            'hours_raw': round(total_hours, 2),
        })
    return results


def compute_date_stats(present_qs, time_qs):
    results = []
    for obj in present_qs:
        user = obj.user
        times_in = time_qs.filter(user=user, out=False)
        times_out = time_qs.filter(user=user, out=True)

        time_in = times_in.first().time if times_in.exists() else None
        time_out = times_out.last().time if times_out.exists() else None

        total_hours = 0.0
        if time_in and time_out:
            total_hours = (time_out - time_in).total_seconds() / 3600

        results.append({
            'username': user.username,
            'full_name': user.get_full_name() or user.username,
            'present': obj.present,
            'time_in': time_in,
            'time_out': time_out,
            'hours': convert_hours_to_str(total_hours),
            'hours_raw': round(total_hours, 2),
        })
    return results


def get_week_data(monday, days=5):
    dates, counts = [], []
    for i in range(days):
        d = monday + datetime.timedelta(days=i)
        cnt = Present.objects.filter(date=d, present=True).count()
        dates.append(str(d))
        counts.append(cnt)
    return dates, counts


def this_week_monday():
    today = datetime.date.today()
    return today - datetime.timedelta(days=today.weekday())


def last_week_monday():
    return this_week_monday() - datetime.timedelta(weeks=1)


# ─────────────────────────────────────────────
# Pages
# ─────────────────────────────────────────────

def home(request):
    return render(request, 'recognition/home.html')


@login_required
def dashboard(request):
    if is_admin(request.user):
        total_emp = User.objects.filter(is_staff=False, is_superuser=False).count()
        today = datetime.date.today()
        present_today = Present.objects.filter(date=today, present=True).count()
        total_records = Present.objects.count()

        tw_mon = this_week_monday()
        lw_mon = last_week_monday()
        tw_dates, tw_counts = get_week_data(tw_mon)
        lw_dates, lw_counts = get_week_data(lw_mon)

        recent = Present.objects.filter(date=today, present=True).select_related('user').order_by('-id')[:10]

        ctx = {
            'total_emp': total_emp,
            'present_today': present_today,
            'total_records': total_records,
            'tw_dates': json.dumps(tw_dates),
            'tw_counts': json.dumps(tw_counts),
            'lw_dates': json.dumps(lw_dates),
            'lw_counts': json.dumps(lw_counts),
            'recent': recent,
            'today': today,
        }
        return render(request, 'recognition/admin_dashboard.html', ctx)
    else:
        today = datetime.date.today()
        user = request.user
        present_today = Present.objects.filter(user=user, date=today, present=True).exists()
        last_time = Time.objects.filter(user=user).order_by('-time').first()
        total_days = Present.objects.filter(user=user, present=True).count()

        tw_mon = this_week_monday()
        my_week = []
        for i in range(5):
            d = tw_mon + datetime.timedelta(days=i)
            pres = Present.objects.filter(user=user, date=d, present=True).exists()
            my_week.append({'date': str(d), 'present': pres})

        ctx = {
            'present_today': present_today,
            'last_time': last_time,
            'total_days': total_days,
            'my_week': my_week,
            'today': today,
        }
        return render(request, 'recognition/employee_dashboard.html', ctx)


@login_required
def add_photos(request):
    if not is_admin(request.user):
        return redirect('not-authorised')
    employees = User.objects.filter(is_staff=False, is_superuser=False)
    photo_counts = {}
    for emp in employees:
        emp_dir = settings.TRAINING_DATASET_DIR / emp.username
        if emp_dir.exists():
            photo_counts[emp.username] = len(list(emp_dir.glob('*.jpg')))
        else:
            photo_counts[emp.username] = 0
    return render(request, 'recognition/add_photos.html', {
        'employees': employees,
        'photo_counts': photo_counts,
        'target': settings.PHOTOS_PER_PERSON,
    })


@login_required
def train(request):
    if not is_admin(request.user):
        return redirect('not-authorised')

    training_dir = settings.TRAINING_DATASET_DIR
    if not training_dir.exists():
        messages.error(request, 'Training dataset directory not found. Please add photos first.')
        return redirect('add-photos')

    try:
        import face_recognition as fr
        X, y = [], []

        for person_name in os.listdir(training_dir):
            person_dir = training_dir / person_name
            if not person_dir.is_dir():
                continue
            for img_file in person_dir.glob('*.jpg'):
                try:
                    image = cv2.imread(str(img_file))
                    if image is None:
                        continue
                    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    encodings = fr.face_encodings(rgb)
                    if encodings:
                        X.append(encodings[0].tolist())
                        y.append(person_name)
                except Exception:
                    img_file.unlink(missing_ok=True)

        if len(X) < 2:
            messages.error(request, 'Not enough training data. Add at least 2 people with photos.')
            return render(request, 'recognition/train.html')

        encoder = LabelEncoder()
        encoder.fit(y)
        y_encoded = encoder.transform(y)
        X_arr = np.array(X)

        settings.FACE_DATA_DIR.mkdir(parents=True, exist_ok=True)
        np.save(str(settings.CLASSES_PATH), encoder.classes_)

        svc = SVC(kernel='linear', probability=True, C=1.0)
        svc.fit(X_arr, y_encoded)

        with open(settings.SVC_MODEL_PATH, 'wb') as f:
            pickle.dump(svc, f)

        messages.success(request, f'Training complete! Model trained on {len(X)} images for {len(encoder.classes_)} people.')
    except Exception as e:
        messages.error(request, f'Training failed: {str(e)}')

    return render(request, 'recognition/train.html', {'trained': True})


@login_required
def mark_attendance_in(request):
    if not model_is_trained():
        messages.warning(request, 'Model not trained yet. Please train the model first.')
        return redirect('train')
    return render(request, 'recognition/mark_attendance.html', {'mode': 'in', 'mode_label': 'Check-In'})


@login_required
def mark_attendance_out(request):
    if not model_is_trained():
        messages.warning(request, 'Model not trained yet. Please train the model first.')
        return redirect('train')
    return render(request, 'recognition/mark_attendance.html', {'mode': 'out', 'mode_label': 'Check-Out'})


@login_required
def view_attendance_home(request):
    today = datetime.date.today()
    total_emp = User.objects.filter(is_staff=False, is_superuser=False).count()
    present_today = Present.objects.filter(date=today, present=True).count()

    tw_mon = this_week_monday()
    lw_mon = last_week_monday()
    tw_dates, tw_counts = get_week_data(tw_mon)
    lw_dates, lw_counts = get_week_data(lw_mon)

    ctx = {
        'total_emp': total_emp,
        'present_today': present_today,
        'today': today,
        'tw_dates': json.dumps(tw_dates),
        'tw_counts': json.dumps(tw_counts),
        'lw_dates': json.dumps(lw_dates),
        'lw_counts': json.dumps(lw_counts),
    }
    return render(request, 'recognition/view_attendance_home.html', ctx)


@login_required
def view_attendance_date(request):
    if not is_admin(request.user):
        return redirect('not-authorised')
    form = DateForm(request.POST or None)
    results = None
    selected_date = None

    if request.method == 'POST' and form.is_valid():
        selected_date = form.cleaned_data['date']
        time_qs = Time.objects.filter(date=selected_date)
        present_qs = Present.objects.filter(date=selected_date).select_related('user')

        if not present_qs.exists():
            messages.warning(request, 'No records found for the selected date.')
        else:
            results = compute_date_stats(present_qs, time_qs)

    return render(request, 'recognition/view_attendance_date.html', {
        'form': form,
        'results': results,
        'selected_date': selected_date,
    })


@login_required
def view_attendance_employee(request):
    if not is_admin(request.user):
        return redirect('not-authorised')
    form = UsernameAndDateForm(request.POST or None)
    results = None
    employee = None
    chart_dates, chart_hours = [], []

    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']

        if date_to < date_from:
            messages.error(request, 'End date must be after start date.')
        elif not User.objects.filter(username=username).exists():
            messages.error(request, f'Employee "{username}" not found.')
        else:
            employee = User.objects.get(username=username)
            present_qs = Present.objects.filter(user=employee, date__gte=date_from, date__lte=date_to).order_by('date')
            time_qs = Time.objects.filter(user=employee, date__gte=date_from, date__lte=date_to)

            if not present_qs.exists():
                messages.warning(request, 'No records found for the selected range.')
            else:
                results = compute_attendance_stats(present_qs, time_qs)
                chart_dates = [str(r['date']) for r in results]
                chart_hours = [r['hours_raw'] for r in results]

    return render(request, 'recognition/view_attendance_employee.html', {
        'form': form,
        'results': results,
        'employee': employee,
        'chart_dates': json.dumps(chart_dates),
        'chart_hours': json.dumps(chart_hours),
    })


@login_required
def view_my_attendance(request):
    if is_admin(request.user):
        return redirect('dashboard')
    form = DateRangeForm(request.POST or None)
    results = None
    chart_dates, chart_hours = [], []

    if request.method == 'POST' and form.is_valid():
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']

        if date_to < date_from:
            messages.error(request, 'End date must be after start date.')
        else:
            user = request.user
            present_qs = Present.objects.filter(user=user, date__gte=date_from, date__lte=date_to).order_by('date')
            time_qs = Time.objects.filter(user=user, date__gte=date_from, date__lte=date_to)

            if not present_qs.exists():
                messages.warning(request, 'No records found for the selected range.')
            else:
                results = compute_attendance_stats(present_qs, time_qs)
                chart_dates = [str(r['date']) for r in results]
                chart_hours = [r['hours_raw'] for r in results]

    return render(request, 'recognition/view_my_attendance.html', {
        'form': form,
        'results': results,
        'chart_dates': json.dumps(chart_dates),
        'chart_hours': json.dumps(chart_hours),
    })


@login_required
def not_authorised(request):
    return render(request, 'recognition/not_authorised.html')


@login_required
def export_csv(request):
    if not is_admin(request.user):
        return redirect('not-authorised')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_export.csv"'

    writer = csv.writer(response)
    writer.writerow(['Employee', 'Date', 'Present', 'Check-In', 'Check-Out'])

    for record in Present.objects.select_related('user').order_by('-date'):
        user = record.user
        times_in = Time.objects.filter(user=user, date=record.date, out=False).order_by('time')
        times_out = Time.objects.filter(user=user, date=record.date, out=True).order_by('time')
        tin = times_in.first().time.strftime('%H:%M:%S') if times_in.exists() else '-'
        tout = times_out.last().time.strftime('%H:%M:%S') if times_out.exists() else '-'
        writer.writerow([user.username, record.date, 'Yes' if record.present else 'No', tin, tout])

    return response


# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────

@csrf_exempt
def api_recognize(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        import face_recognition as fr
        data = json.loads(request.body)
        image_b64 = data.get('image', '').split(',')[-1]
        if not image_b64:
            return JsonResponse({'error': 'No image provided'}, status=400)

        image_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return JsonResponse({'error': 'Invalid image data'}, status=400)

        if not model_is_trained():
            return JsonResponse({'error': 'Model not trained'}, status=400)

        svc, encoder = load_model()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locs = fr.face_locations(rgb, model='hog')

        if not face_locs:
            return JsonResponse({'recognized': False, 'message': 'No face detected'})

        face_encs = fr.face_encodings(rgb, face_locs)
        faces = []
        for enc, loc in zip(face_encs, face_locs):
            prob = svc.predict_proba([enc])[0]
            max_prob = float(np.max(prob))
            if max_prob >= settings.RECOGNITION_THRESHOLD:
                pred_idx = int(np.argmax(prob))
                name = str(encoder.inverse_transform([pred_idx])[0])
                faces.append({'name': name, 'confidence': round(max_prob, 3), 'location': list(loc)})
            else:
                faces.append({'name': 'Unknown', 'confidence': round(max_prob, 3), 'location': list(loc)})

        return JsonResponse({'recognized': len(faces) > 0, 'faces': faces})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def api_capture_photo(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not is_admin(request.user):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        image_b64 = data.get('image', '').split(',')[-1]

        if not username or not image_b64:
            return JsonResponse({'error': 'Missing username or image'}, status=400)

        if not User.objects.filter(username=username).exists():
            return JsonResponse({'error': f'User "{username}" not found'}, status=404)

        save_dir = settings.TRAINING_DATASET_DIR / username
        save_dir.mkdir(parents=True, exist_ok=True)

        existing = len(list(save_dir.glob('*.jpg')))
        if existing >= settings.PHOTOS_PER_PERSON:
            return JsonResponse({'success': True, 'count': existing, 'done': True})

        image_bytes = base64.b64decode(image_b64)
        nparr = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            return JsonResponse({'error': 'Invalid image'}, status=400)

        count = existing + 1
        cv2.imwrite(str(save_dir / f'{count}.jpg'), frame)

        done = count >= settings.PHOTOS_PER_PERSON
        return JsonResponse({'success': True, 'count': count, 'done': done, 'target': settings.PHOTOS_PER_PERSON})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def api_mark_attendance(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        mode = data.get('mode', 'in')

        if not username:
            return JsonResponse({'error': 'Username required'}, status=400)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return JsonResponse({'error': f'User "{username}" not found'}, status=404)

        today = datetime.date.today()
        now = datetime.datetime.now()

        if mode == 'in':
            present, _ = Present.objects.get_or_create(user=user, date=today)
            present.present = True
            present.save()
            Time.objects.create(user=user, date=today, time=now, out=False)
            msg = f'Check-In recorded for {user.get_full_name() or username}'
        else:
            Time.objects.create(user=user, date=today, time=now, out=True)
            msg = f'Check-Out recorded for {user.get_full_name() or username}'

        return JsonResponse({'success': True, 'message': msg, 'time': now.strftime('%H:%M:%S')})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_model_status(request):
    trained = model_is_trained()
    people = []
    if settings.TRAINING_DATASET_DIR.exists():
        for person_dir in settings.TRAINING_DATASET_DIR.iterdir():
            if person_dir.is_dir():
                count = len(list(person_dir.glob('*.jpg')))
                people.append({'name': person_dir.name, 'photos': count})
    return JsonResponse({'trained': trained, 'people': people})
