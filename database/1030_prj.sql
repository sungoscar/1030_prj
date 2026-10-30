SELECT
    a.activity_name,
    r.name,
    r.phone,
    r.registration_date
FROM activity a
JOIN registration r
ON a.activity_id = r.activity_id
WHERE a.activity_id = 1;