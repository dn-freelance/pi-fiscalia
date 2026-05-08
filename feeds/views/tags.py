import re

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from feeds.models import Tag


def index(request):
    context = {
        'tags': Tag.objects.all(),
        'tag_color_choices': Tag.COLOR_CHOICES,
    }
    return render(request, 'pages/tags/index.html', context)


@require_POST
def create_tag(request):
    tag_data = _tag_payload_from_request(request)
    is_valid, error_message = _tag_payload_is_valid(tag_data)

    if not is_valid:
        messages.error(request, error_message)
        return redirect('feeds:tags')

    tag = Tag()
    saved, error_message = _save_tag(tag, tag_data)

    if not saved:
        messages.error(request, error_message)
        return redirect('feeds:tags')

    messages.success(request, f'Tag "{tag.name}" cadastrada com sucesso.')
    return redirect('feeds:tags')


@require_POST
def update_tag(request, tag_id):
    tag_data = _tag_payload_from_request(request)
    is_valid, error_message = _tag_payload_is_valid(tag_data)

    if not is_valid:
        messages.error(request, error_message)
        return redirect('feeds:tags')

    tag = get_object_or_404(Tag, pk=tag_id)
    saved, error_message = _save_tag(tag, tag_data)

    if not saved:
        messages.error(request, error_message)
        return redirect('feeds:tags')

    messages.success(request, f'Tag "{tag.name}" atualizada com sucesso.')
    return redirect('feeds:tags')


@require_POST
def delete_tag(request, tag_id):
    tag = get_object_or_404(Tag, pk=tag_id)
    name = tag.name

    tag.delete()
    messages.success(request, f'Tag "{name}" excluída com sucesso.')

    return redirect('feeds:tags')


def _tag_payload_from_request(request):
    return {
        'name': request.POST.get('name', '').strip(),
        'color': request.POST.get('color', '').strip().lower(),
    }


def _tag_payload_is_valid(tag_data):
    if not tag_data['name']:
        return False, 'O nome da tag não pode estar vazio.'

    if not _is_valid_tag_name(tag_data['name']):
        return False, 'O nome da tag contém caracteres inválidos.'

    if not _is_valid_color(tag_data['color']):
        return False, 'Selecione uma cor válida para a tag.'

    return True, ''


def _is_valid_tag_name(name):
    allowed_name_pattern = re.compile(r'^[A-Za-zÀ-ÿ0-9\s\-/&()]+$')
    return bool(allowed_name_pattern.match(name))


def _is_valid_color(color):
    return color in dict(Tag.COLOR_CHOICES)


def _save_tag(tag, tag_data):
    tag.name = tag_data['name']
    tag.color = tag_data['color']

    # Check for duplicate name (excluding current tag if updating)
    existing_tag = Tag.objects.filter(name__iexact=tag_data['name']).exclude(pk=tag.pk).first()
    if existing_tag:
        return False, 'Já existe uma tag cadastrada com este nome.'

    try:
        tag.full_clean()
        tag.save()
    except ValidationError as error:
        return False, _validation_error_message(error)
    except IntegrityError:
        return False, 'Já existe uma tag cadastrada com este nome.'

    return True, ''


def _validation_error_message(error):
    if hasattr(error, 'message_dict'):
        if 'name' in error.message_dict:
            # Check if it's a unique constraint violation
            if 'already exists' in str(error.message_dict.get('name', [])):
                return 'Já existe uma tag cadastrada com este nome.'
            return 'O nome da tag contém caracteres inválidos.'
        if 'color' in error.message_dict:
            return 'Selecione uma cor válida para a tag.'

    return 'Não foi possível salvar a tag. Revise os dados informados.'
