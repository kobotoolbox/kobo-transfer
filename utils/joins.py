def left_join(left_list, right_list, on):
    return [
        {
            **item_left,
            **next(
                (
                    item_right
                    for item_right in right_list
                    if item_right[on] == item_left[on]
                ),
                {},
            ),
        }
        for item_left in left_list
    ]
