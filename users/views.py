from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required


@login_required
def register(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return redirect('not-authorised')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = False
            user.save()
            messages.success(request, f'Employee "{user.username}" registered successfully!')
            return redirect('dashboard')
    else:
        form = UserCreationForm()

    return render(request, 'users/register.html', {'form': form})
