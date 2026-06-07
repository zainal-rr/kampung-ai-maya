from __future__ import annotations

import re

from travel_budget_style import _add_table


def _food_restaurant_section(ws, plan: dict, template_mode: bool) -> tuple[int, int]:
    ws.append(["Food And Restaurant Plan", "", "", "", "", "", "", "", "", ""])
    ws.append(["Day", "Restaurant / Area", "Food Item", "Estimated Cost MYR", "Actual Cost MYR", "Variance MYR", "Source Link", "Notes", "Suggestion", "Priority"])
    header_row = ws.max_row
    first_row = ws.max_row + 1
    rows = _food_restaurant_rows(plan, template_mode)
    for item in rows:
        row_num = ws.max_row + 1
        source_link = item["source"]
        ws.append([
            item["day"],
            item["place"],
            item["food"],
            item["estimate"],
            "",
            f'=IF(OR(D{row_num}="",E{row_num}=""),"",E{row_num}-D{row_num})',
            source_link,
            item["notes"],
            item["suggestion"],
            item["priority"],
        ])
        ws.cell(row=row_num, column=7).hyperlink = source_link
        ws.cell(row=row_num, column=7).style = "Hyperlink"
    last_row = ws.max_row
    total_row = ws.max_row + 1
    ws.append([
        "Total",
        "",
        "",
        f"=SUM(D{first_row}:D{last_row})",
        f"=SUM(E{first_row}:E{last_row})",
        f"=SUM(F{first_row}:F{last_row})",
        "",
        "Food and restaurant totals",
        "Use variance to compare plan against actual spend",
        "",
    ])
    _add_table(ws, "FoodRestaurantPlan", f"A{header_row}:J{total_row}")
    return first_row, total_row


def _food_restaurant_rows(plan: dict, template_mode: bool) -> list[dict[str, object]]:
    if template_mode:
        return [
            _food_row("Day 1", "Restaurant / market", "Signature dish", 0, "", "Add source or map link", "Add why this stop matters", "High"),
            _food_row("Day 1", "Cafe / dessert", "Dessert or drink", 0, "", "Add source or map link", "Good optional stop", "Medium"),
            _food_row("Day 2", "Local restaurant", "Main meal", 0, "", "Add source or map link", "Reserve or queue early if popular", "High"),
            _food_row("Day 2", "Street food area", "Snack crawl", 0, "", "Add source or map link", "Keep cash/card notes here", "Medium"),
        ]
    destination = str(plan.get("destination") or "").strip().lower()
    if "seoul" in destination:
        return [
            _food_row("Day 1", "Myeongdong Kyoja", "Kalguksu and mandu", 45, "https://www.google.com/maps/search/?api=1&query=Myeongdong+Kyoja+Seoul", "Classic central Seoul noodle stop", "Go early or off-peak to avoid queues", "High"),
            _food_row("Day 1", "Gwangjang Market", "Bindaetteok, mayak gimbap, tteokbokki", 55, "https://www.google.com/maps/search/?api=1&query=Gwangjang+Market+Seoul", "Market-style food crawl", "Share dishes so you can try more items", "High"),
            _food_row("Day 1", "Cafe Onion Anguk", "Pastries and coffee", 35, "https://www.google.com/maps/search/?api=1&query=Cafe+Onion+Anguk+Seoul", "Good cafe stop near Bukchon/Anguk", "Use as a rest stop between walks", "Medium"),
            _food_row("Day 2", "Tosokchon Samgyetang", "Ginseng chicken soup", 55, "https://www.google.com/maps/search/?api=1&query=Tosokchon+Samgyetang+Seoul", "Near Gyeongbokgung area", "Best as lunch after palace visit", "High"),
            _food_row("Day 2", "Jin Ok Hwa Original Chicken", "Dakhanmari", 60, "https://www.google.com/maps/search/?api=1&query=Jin+Ok+Hwa+Original+Chicken+Seoul", "Hearty shared chicken meal", "Good dinner if traveling with others", "Medium"),
            _food_row("Day 2", "Maple Tree House Itaewon", "Korean BBQ", 90, "https://www.google.com/maps/search/?api=1&query=Maple+Tree+House+Itaewon+Seoul", "Higher-budget BBQ option", "Use as the splurge meal if budget allows", "Optional"),
            _food_row("Flexible", "Isaac Toast", "Breakfast toast", 20, "https://www.google.com/maps/search/?api=1&query=Isaac+Toast+Seoul", "Fast breakfast/snack option", "Use when the itinerary needs a quick meal", "Medium"),
        ]
    if "tokyo" in destination:
        return [
            _food_row("Day 1", "Tsukiji Outer Market", "Seafood bowl, tamagoyaki, grilled skewers", 90, "https://www.google.com/maps/search/?api=1&query=Tsukiji+Outer+Market+Tokyo", "Classic market crawl with many small bites", "Go early and share items to avoid overspending", "High"),
            _food_row("Day 1", "Ichiran Shibuya", "Tonkotsu ramen", 55, "https://www.google.com/maps/search/?api=1&query=Ichiran+Shibuya+Tokyo", "Easy solo-friendly ramen stop", "Use as a reliable backup if plans slip", "Medium"),
            _food_row("Day 1", "Uobei Shibuya Dogenzaka", "Conveyor sushi", 60, "https://www.google.com/maps/search/?api=1&query=Uobei+Shibuya+Dogenzaka+Tokyo", "Fast sushi with predictable pricing", "Good for a controlled-budget dinner", "Medium"),
            _food_row("Day 2", "Gyukatsu Motomura Shinjuku", "Beef cutlet set", 75, "https://www.google.com/maps/search/?api=1&query=Gyukatsu+Motomura+Shinjuku+Tokyo", "Popular beef cutlet meal", "Queue before peak dinner or keep a backup nearby", "High"),
            _food_row("Day 2", "Afuri Harajuku", "Yuzu shio ramen", 55, "https://www.google.com/maps/search/?api=1&query=Afuri+Harajuku+Tokyo", "Lighter ramen near Harajuku/Omotesando", "Works well between shopping and cafe stops", "Medium"),
            _food_row("Day 2", "Tonkatsu Maisen Aoyama", "Tonkatsu set", 70, "https://www.google.com/maps/search/?api=1&query=Tonkatsu+Maisen+Aoyama+Tokyo", "Classic tonkatsu option", "Use as the splurge if skipping gyukatsu", "Optional"),
            _food_row("Flexible", "Lawson or 7-Eleven Tokyo", "Onigiri, sandwich, drink", 25, "https://www.google.com/maps/search/?api=1&query=Lawson+Tokyo", "Convenience store breakfast or late snack", "Keep this as the cheap buffer meal", "Medium"),
        ]
    place = str(plan.get("destination") or "Destination").strip() or "Destination"
    return [
        _food_row("Day 1", f"{place} signature restaurant", "Signature local dish", 50, _maps_search(f"{place} best restaurant signature dish"), "Replace with chosen restaurant", "Pick one must-try local dish", "High"),
        _food_row("Day 1", f"{place} market or street food area", "Snack crawl", 40, _maps_search(f"{place} market street food"), "Good for variety", "Share small portions to try more", "Medium"),
        _food_row("Day 2", f"{place} cafe or dessert stop", "Coffee, dessert, or local sweets", 30, _maps_search(f"{place} best cafe dessert"), "Rest stop between sightseeing", "Choose based on route convenience", "Medium"),
        _food_row("Day 2", f"{place} dinner restaurant", "Main dinner", 70, _maps_search(f"{place} recommended dinner restaurant"), "Main meal of the day", "Reserve or plan queue time if popular", "High"),
    ]


def _food_row(day: str, place: str, food: str, estimate: int, source: str, notes: str, suggestion: str, priority: str) -> dict[str, object]:
    return {
        "day": day,
        "place": place,
        "food": food,
        "estimate": estimate,
        "source": source,
        "notes": notes,
        "suggestion": suggestion,
        "priority": priority,
    }


def _maps_search(query: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + re.sub(r"\s+", "+", query.strip())
