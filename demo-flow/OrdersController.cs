using System;
class RouteAttribute : Attribute { public RouteAttribute(string route) {} }
class HttpPostAttribute : Attribute {}
[Route("api/orders")]
public class OrdersController {
    private OrdersService service = new OrdersService();
    [HttpPost]
    public void Create() { service.Save(); }
}
public class OrdersService {
    public void Save() {}
}
