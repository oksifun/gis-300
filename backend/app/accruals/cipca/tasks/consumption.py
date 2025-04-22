from app.accruals.pipca.processing import prepare_document_for_calculation


def set_consumption_methods_func(author_id, doc_id):
    # подготовить документ начислений для расчёта
    doc = prepare_document_for_calculation(
        'set_consumption_methods',
        author_id,
        doc_id,
    )
    # определить методы
    for debt in doc.debts:
        doc.set_consumption_methods(debt)
        debt.changed = True
    # сохранить
    doc.save()
