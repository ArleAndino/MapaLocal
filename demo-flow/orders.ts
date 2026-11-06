import { OrdersService } from './service';
function Component(options: any) { return (type: any) => type; }
@Component({ templateUrl: './orders.html' })
export class OrdersComponent {
  constructor(private service: OrdersService) {}
  save() { this.service.create(); }
}
