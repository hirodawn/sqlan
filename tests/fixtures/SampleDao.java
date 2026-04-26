package com.example.dao;

public class SampleDao {

    private JdbcManager jdbcManager;

    public List<Employee> findAll() {
        return jdbcManager.selectBySql(Employee.class,
            "META-INF/sql/select_employee.sql").getResultList();
    }

    public Employee findById(Integer id) {
        return jdbcManager.selectBySql(Employee.class,
            "META-INF/sql/select_with_join.sql", id).getSingleResult();
    }

    public int update(EmployeeDto dto) {
        return jdbcManager.updateBySql(
            "META-INF/sql/update_employee.sql", dto.getClass()).execute();
    }

    public int insert(Employee entity) {
        return jdbcManager.insertBySql(
            "META-INF/sql/insert_employee.sql", entity.getClass()).execute();
    }
}
