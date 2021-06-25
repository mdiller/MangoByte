def get_hero_winrate(hero):
    """returns hero winrate from list of meta heroes"""
    if hero['pro_pick'] == 0: return 0
    else: return hero.get('pro_win', 0) / hero.get('pro_pick', 1)


def get_hero_pick_percent(hero, heroes):
    return hero.get('pro_pick', 0) / get_total_pro_games(heroes)


def get_hero_ban_percent(hero, heroes):
    return hero.get('pro_ban', 0) / get_total_pro_games(heroes)


def get_total_pro_games(heroes):
    total = 0
    for hero in heroes:
        total += hero.get('pro_pick', 0)  # sums total games in the list
    total = total/10
    return total

def get_hero_pickban_percent(hero, heroes):
    return (
        hero.get('pro_pick', 0) + hero.get('pro_ban', 0)
    ) / get_total_pro_games(heroes)
