
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        churn_label as value_field,
        count(*) as n_records

    from "iceberg"."analytics"."customer_360"
    group by churn_label

)

select *
from all_values
where value_field not in (
    0,1
)



  
  
      
    ) dbt_internal_test