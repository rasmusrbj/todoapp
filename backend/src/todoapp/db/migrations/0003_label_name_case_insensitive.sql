-- 0003_label_name_case_insensitive.sql
--
-- `labels.name` is plain text, so `UNIQUE (list_id, name)` from 0001 let "Haster"
-- and "haster" coexist on one list. Two labels that look identical in the UI is a
-- bug, not a feature, so uniqueness is folded to lower case.
--
-- The column stays `text` rather than becoming `citext`: the display casing the
-- user typed is worth keeping, and only the *constraint* needs to ignore it.

-- Collapse any pre-existing duplicates, keeping the oldest row of each group and
-- moving its tasks over, so the new index can be created.
WITH ranked AS (
    SELECT id,
           list_id,
           lower(name) AS folded,
           first_value(id) OVER (
               PARTITION BY list_id, lower(name) ORDER BY created_at, id
           ) AS keep_id
    FROM labels
),
duplicates AS (
    SELECT id, keep_id FROM ranked WHERE id <> keep_id
)
UPDATE task_labels tl
SET label_id = d.keep_id
FROM duplicates d
WHERE tl.label_id = d.id
  -- Skip rows that would collide with a link the surviving label already has.
  AND NOT EXISTS (
      SELECT 1 FROM task_labels existing
      WHERE existing.task_id = tl.task_id AND existing.label_id = d.keep_id
  );

DELETE FROM labels
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               first_value(id) OVER (
                   PARTITION BY list_id, lower(name) ORDER BY created_at, id
               ) AS keep_id
        FROM labels
    ) ranked
    WHERE id <> keep_id
);

ALTER TABLE labels DROP CONSTRAINT labels_list_id_name_key;

CREATE UNIQUE INDEX labels_list_id_lower_name_idx ON labels (list_id, lower(name));
