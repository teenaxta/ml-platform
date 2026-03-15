
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select total_orders
from "iceberg"."analytics"."customer_360"
where total_orders is null



  
  
      
    ) dbt_internal_test