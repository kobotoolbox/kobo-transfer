def left_join(left_list, right_list, on):
    # Indexed: a nested scan is quadratic, minutes for projects of tens of thousands
    right = {}
    for item in right_list:
        right.setdefault(item[on], item)
    return [{**item_left, **right.get(item_left[on], {})} for item_left in left_list]
