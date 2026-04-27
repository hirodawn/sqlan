UPDATE employee
SET
  name = department.department_name,
  department_id = /*dto.deptId*/1
FROM department
WHERE employee.department_id = department.department_id
  AND employee.employee_id = /*dto.employeeId*/1
