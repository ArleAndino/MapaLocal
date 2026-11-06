using Demo.Services;
namespace Demo.Controllers;
public class UsersController {
    private readonly UserService service;
    public UsersController(UserService service) { this.service = service; }
    public string Get() { return service.List(); }
}
