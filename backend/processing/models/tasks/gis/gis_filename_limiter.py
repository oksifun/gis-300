def limit_xlsx_filename(filename, some_id="", address="", doc_type=""):
    """
    Ограничевает длинну имени файла так, чтобы
    не был превышен лимит, утсановленный OS.
    Добавляет в конце расширение .xlsx
    """
    # Формируем строку из тех полей, которые переданы,
    # урезаем id вполовину. Расширение добавляем в конце,
    # чтобы не оставлять пробелов перед ним при отсутсвии
    # адреса и ид
    filename_new = "{} {} {}".format(filename,
                                     address,
                                     some_id[int(len(some_id) / 2):] if some_id else ""
                                     ).strip() + ".xlsx"

    # Проверяем не превышает ли имя допустимые размер
    while (doc_type + filename_new).__sizeof__() > 252:
        # Если да, срезаем начало
        filename_new = filename_new[1:]
    if doc_type:
        return (doc_type + " " + filename_new).replace('/', ' ')
    else:
        return filename_new.replace('/', ' ')



if __name__ == '__main__':
    name = "ООО ««УК Стройлинк-сервис»»"
    print(limit_xlsx_filename(name,
                              str(234243432424242424),
                              "г Санкт-Петербург, пр-кт Художников, д. 24 корп. 4/5", doc_type="МКД"))
    print(limit_xlsx_filename(filename=name,
                              address="г Санкт-Петербург, пр-кт Художников, д. 24 корп. 4/5", doc_type="МКД"))
