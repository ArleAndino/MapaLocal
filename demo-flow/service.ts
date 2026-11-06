class HttpClient { post(url: string, body: unknown) {} }
export class OrdersService {
  constructor(private http: HttpClient) {}
  create() { this.http.post('/api/orders', {}); }
}
