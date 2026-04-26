SELECT
  e.employee_id,
  e.name,
  d.department_name
FROM
  employee e
  INNER JOIN department d ON e.department_id = d.department_id
/*BEGIN*/
WHERE
  /*IF dto.name != null*/
  e.name LIKE /*dto.name*/'%test%'
  /*END*/
/*END*/
