from app.utils.safety import pre_filter, map_interaction_mode_to_age


def test_map_interaction_mode_to_age():
    assert map_interaction_mode_to_age('Young Learner (5–11)') == 'kids'
    assert map_interaction_mode_to_age('Young Adult (11–16)') == 'teen'
    assert map_interaction_mode_to_age('Student (16–21)') == 'general'
    assert map_interaction_mode_to_age('Master') == 'general'


def test_pre_filter_blocks_for_kids():
    blocked, _ = pre_filter('this is explicit sex content', 'kids')
    assert blocked is True
    blocked, _ = pre_filter('friendly hello world', 'kids')
    assert blocked is False
