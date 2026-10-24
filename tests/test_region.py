from scope import Region, search_areas


def test_search_areas():
    home = {"wo": "Regensburg", "umkreis": 50}
    assert search_areas({"home": home}) == [home, {}]                     # home + nationwide, as before
    more = [{"wo": "München", "umkreis": 50}, home]
    assert search_areas({"home": home, "areas": more}) == [home, more[0]]  # no nationwide pass, no duplicates
    assert search_areas(None) == [{}]


def test_region_filter():
    r = Region({"regions": ["Bayern"], "region_plz": ["8", "9"], "region_places": ["Regensburg"]})
    assert r.keep({"region": "Bayern", "location": "Berlin"})            # the ad's region wins
    assert not r.keep({"region": "Berlin"})
    assert r.keep({"plz": "93055"}) and not r.keep({"plz": "10115", "location": "Berlin"})
    assert r.keep({"location": "Munich, Bavaria"}) and r.keep({"location": "Regensburg"})
    assert not r.keep({"location": "Hamburg"})
    job = {"location": ""}
    assert r.keep(job) and job["location_check"]                          # unknown: kept, marked for scoring
    assert Region({}).keep({"location": "Hamburg"})                       # no regions: everything stays
