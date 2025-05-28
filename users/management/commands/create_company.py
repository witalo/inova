from django.core.management import CommandError, BaseCommand
from users.models import Company


class Command(BaseCommand):
    help = 'Crear una nueva empresa'

    def add_arguments(self, parser):
        parser.add_argument('--ruc', type=str, required=True, help='RUC de la empresa')
        parser.add_argument('--denomination', type=str, required=True, help='Razón social')
        parser.add_argument('--email', type=str, required=True, help='Correo de la empresa')
        parser.add_argument('--password', type=str, required=True, help='Contraseña')
        parser.add_argument('--address', type=str, help='Dirección')
        parser.add_argument('--phone', type=str, help='Teléfono')

    def handle(self, *args, **options):
        try:
            # Validar que no exista la empresa
            if Company.objects.filter(ruc=options['ruc']).exists():
                raise CommandError(f'Ya existe una empresa con RUC {options["ruc"]}')

            if Company.objects.filter(email=options['email']).exists():
                raise CommandError(f'Ya existe una empresa con email {options["email"]}')

            # Crear empresa
            company = Company(
                ruc=options['ruc'],
                denomination=options['denomination'],
                email=options['email'],
                address=options.get('address', ''),
                phone=options.get('phone', '')
            )
            company.set_password(options['password'])
            company.save()

            self.stdout.write(
                self.style.SUCCESS(f'Empresa "{company.denomination}" creada exitosamente')
            )

        except Exception as e:
            raise CommandError(f'Error al crear empresa: {str(e)}')

# # Crear empresa de ejemplo
# python manage.py create_company --ruc=10461181649 --denomination="INOVA" --email="vent.wivf@gmail.com" --password="italo" --address="Av. Vidaurrazaga" --phone="989982265"
# # Crear superusuario
# python manage.py createsuperuser