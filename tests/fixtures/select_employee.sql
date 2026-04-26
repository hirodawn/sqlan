SELECT
  e.employee_id,
  e.name
FROM
  employee e
/*BEGIN*/
WHERE
  /*IF dto.departmentId != null*/
  e.department_id = /*dto.departmentId*/1
  /*END*/
  /*IF dto.name != null*/
  AND e.name LIKE /*dto.name*/'%test%'
  /*END*/
/*END*/
ORDER BY e.employee_id
