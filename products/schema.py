from datetime import datetime

import graphene
from products.models import Product, TypeAffectation, Unit
from products.mutations import ProductMutation, DeleteProductMutation
from products.types import ProductType, TypeAffectationType, UnitType
from graphene_django import DjangoObjectType
from django.db.models import Q, Value, IntegerField, Case, When, F
from django.db.models.functions import Lower
import re
from difflib import SequenceMatcher
from .models import Product


class ProductsQuery(graphene.ObjectType):
    products_by_company_id = graphene.List(ProductType, company_id=graphene.ID(required=True))
    search_products = graphene.List(
        ProductType,
        search=graphene.String(required=True),
        company_id=graphene.ID(required=True),
        limit=graphene.Int(default_value=20)
    )
    # Obtener producto por ID
    product_by_id = graphene.Field(
        ProductType,
        id=graphene.ID(required=True),
        company_id=graphene.ID(required=True)
    )
    type_affectations = graphene.List(TypeAffectationType)
    units = graphene.List(UnitType)

    @staticmethod
    def resolve_products_by_company_id(self, info, company_id=None):
        return Product.objects.filter(is_active=True, company_id=company_id).order_by('id')

    def resolve_search_products(self, info, search, company_id, limit=20):
        """
        Búsqueda ultra eficiente tipo YouTube con tolerancia a errores
        """
        search = search.strip().lower()
        if not search or len(search) < 2:
            return []

        # Limpiar caracteres especiales pero mantener espacios
        search_clean = re.sub(r'[^\w\s]', '', search)
        words = search_clean.split()

        if not words:
            return []

        # ESTRATEGIA 1: Búsqueda exacta (más rápida)
        exact_query = Q(code__iexact=search) | Q(description__iexact=search)

        # ESTRATEGIA 2: Contiene la frase completa
        phrase_query = Q(code__icontains=search) | Q(description__icontains=search)

        # ESTRATEGIA 3: Todas las palabras presentes (AND)
        all_words_query = Q()
        for word in words:
            all_words_query &= (Q(description__icontains=word) | Q(code__icontains=word))

        # ESTRATEGIA 4: Búsqueda flexible - al menos UNA palabra coincide
        any_word_query = Q()
        for word in words:
            if len(word) >= 2:  # Ignorar palabras muy cortas
                any_word_query |= (Q(description__icontains=word) | Q(code__icontains=word))

        # ESTRATEGIA 5: Prefijos - para autocompletado rápido
        prefix_query = Q()
        first_word = words[0]
        if len(first_word) >= 2:
            prefix_query = Q(description__istartswith=first_word) | Q(code__istartswith=first_word)

        # Obtener productos base
        base_queryset = Product.objects.filter(
            company_id=company_id,
            is_active=True
        )

        # Ejecutar búsqueda con scoring
        products = base_queryset.annotate(
            # Score basado en tipo de coincidencia
            relevance_score=Case(
                # Coincidencia exacta = 100 puntos
                When(exact_query, then=Value(100)),
                # Contiene frase completa = 90 puntos
                When(phrase_query, then=Value(90)),
                # Todas las palabras = 80 puntos
                When(all_words_query, then=Value(80)),
                # Empieza con la primera palabra = 70 puntos
                When(prefix_query, then=Value(70)),
                # Al menos una palabra = 50 puntos
                When(any_word_query, then=Value(50)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).filter(
            relevance_score__gt=0  # Solo resultados relevantes
        ).order_by('-relevance_score', 'description')[:limit * 2]  # Traer más para filtrar

        # OPTIMIZACIÓN: Si ya tenemos buenos resultados, retornarlos
        if len(products) <= limit:
            return products

        # ESTRATEGIA 6: Similitud fuzzy para los top resultados (tolerancia a errores)
        # Solo si necesitamos refinar resultados
        scored_products = []
        for product in products:
            # Calcular similitud con la búsqueda
            desc_lower = product.description.lower() if product.description else ""
            code_lower = product.code.lower() if product.code else ""

            # Similitud básica rápida
            desc_similarity = self._quick_similarity(search, desc_lower)
            code_similarity = self._quick_similarity(search, code_lower)

            # Bonus si contiene todas las palabras en orden
            order_bonus = 10 if all(word in desc_lower for word in words) else 0

            # Score final
            final_score = product.relevance_score + (max(desc_similarity, code_similarity) * 20) + order_bonus

            scored_products.append({
                'product': product,
                'score': final_score
            })

        # Ordenar por score final y tomar los mejores
        scored_products.sort(key=lambda x: x['score'], reverse=True)
        final_results = [item['product'] for item in scored_products[:limit]]

        # Asignar score para mostrar en frontend si quieres
        for i, product in enumerate(final_results):
            product.relevance_score = scored_products[i]['score']

        return final_results

    @staticmethod
    def _quick_similarity(self, search, text):
        """Cálculo rápido de similitud (0-1)"""
        if not text:
            return 0

        # Si contiene la búsqueda exacta
        if search in text:
            return 1.0

        # Similitud por caracteres comunes (más rápido que SequenceMatcher)
        common = 0
        for char in search:
            if char in text:
                common += 1

        return common / len(search) if search else 0

    @staticmethod
    def resolve_product_by_id(self, info, id, company_id):
        try:
            return Product.objects.select_related(
                'type_affectation',
                'unit'
            ).get(
                id=id,
                company_id=company_id
            )
        except Product.DoesNotExist:
            return None

    @staticmethod
    def resolve_type_affectations(self, info):
        return TypeAffectation.objects.all().order_by('code')

    @staticmethod
    def resolve_units(self, info):
        return Unit.objects.all().order_by('id')


class ProductsMutation(graphene.ObjectType):
    save_product = ProductMutation.Field()
    delete_product = DeleteProductMutation.Field()
