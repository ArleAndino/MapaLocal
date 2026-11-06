import { Component } from '@angular/core';
import { UserService } from '@app/user.service';
@Component({selector: 'app-root', template: '<h1>Usuarios</h1>', styleUrls: ['./app.component.scss']})
export class AppComponent {
  constructor(private users: UserService) {}
  async loadUsers() { return this.users.list(); }
}
