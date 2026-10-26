-- Private read-out of the CoachBadge page counter (Supabase SQL editor or the Supabase connector). Days are Zurich time.
-- 1. Views per day
select day, sum(views) as views from public.coachbadge_page_views where day >= current_date - 27 group by day order by day desc;
-- 2. Top pages
select path, sum(views) as views from public.coachbadge_page_views where day >= current_date - 27 group by path order by views desc limit 30;
-- 3. Referrer domains ('' = direct, bookmarks, or no referrer sent)
select ref_domain, sum(views) as views from public.coachbadge_page_views where day >= current_date - 27 group by ref_domain order by views desc;
-- 4. Tagged links
select utm_source, utm_medium, utm_campaign, sum(views) as views from public.coachbadge_page_views
where day >= current_date - 27 and (utm_source <> '' or utm_medium <> '' or utm_campaign <> '') group by 1,2,3 order by views desc;
