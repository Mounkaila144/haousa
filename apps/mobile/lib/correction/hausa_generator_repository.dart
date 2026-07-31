import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:hausa_mobile/network/api_client.dart';

/// Forme hausa canonique d'un nombre, générée **exclusivement** par le moteur
/// via l'API (`GET /grammar/generate/{n}`). Aucune règle numérique côté client.
class HausaGeneration {
  const HausaGeneration({
    required this.number,
    required this.hausaText,
    required this.grammarVersion,
  });

  factory HausaGeneration.fromJson(Map<String, dynamic> json) {
    final Object? number = json['number'];
    final Object? hausaText = json['hausa_text'];
    final Object? grammarVersion = json['grammar_version'];
    if (number is! num ||
        hausaText is! String ||
        hausaText.isEmpty ||
        grammarVersion is! String ||
        grammarVersion.isEmpty) {
      throw const GenerationContractException();
    }
    return HausaGeneration(
      number: number.toInt(),
      hausaText: hausaText,
      grammarVersion: grammarVersion,
    );
  }

  final int number;
  final String hausaText;
  final String grammarVersion;
}

class GenerationContractException implements Exception {
  const GenerationContractException();
}

enum GenerationFailureType {
  outOfRange,
  unavailable,
  timeout,
  noConnection,
  cancelled,
  invalidResponse,
  unknown,
}

class GenerationFailure implements Exception {
  const GenerationFailure({
    required this.type,
    required this.message,
    this.statusCode,
    this.code,
  });

  final GenerationFailureType type;
  final String message;
  final int? statusCode;
  final String? code;

  bool get isCancelled => type == GenerationFailureType.cancelled;

  @override
  String toString() => message;
}

abstract interface class HausaGeneratorRepository {
  Future<HausaGeneration> generate({
    required int number,
    required CancelToken cancelToken,
  });
}

class DioHausaGeneratorRepository implements HausaGeneratorRepository {
  const DioHausaGeneratorRepository(this._dio);

  final Dio _dio;

  @override
  Future<HausaGeneration> generate({
    required int number,
    required CancelToken cancelToken,
  }) async {
    try {
      final Response<dynamic> response = await _dio.get<dynamic>(
        '/grammar/generate/$number',
        cancelToken: cancelToken,
      );
      final Object? data = response.data;
      if (data is! Map<String, dynamic>) {
        throw const GenerationContractException();
      }
      final HausaGeneration generation = HausaGeneration.fromJson(data);
      if (generation.number != number) {
        throw const GenerationContractException();
      }
      return generation;
    } on DioException catch (error) {
      throw _generationFailure(normalizeNetworkFailure(error));
    } on GenerationContractException {
      throw const GenerationFailure(
        type: GenerationFailureType.invalidResponse,
        message: 'La forme hausa reçue est invalide.',
      );
    }
  }
}

final hausaGeneratorRepositoryProvider = Provider<HausaGeneratorRepository>((
  ref,
) {
  return DioHausaGeneratorRepository(ref.watch(dioProvider));
});

GenerationFailure _generationFailure(NetworkFailure failure) {
  final int? status = failure.statusCode;
  final String? code = failure.code;
  final GenerationFailureType type;
  final String message;

  if (failure.type == NetworkFailureType.cancelled) {
    type = GenerationFailureType.cancelled;
    message = '';
  } else if (failure.type == NetworkFailureType.timeout ||
      failure.type == NetworkFailureType.noConnection) {
    type = failure.type == NetworkFailureType.timeout
        ? GenerationFailureType.timeout
        : GenerationFailureType.noConnection;
    message = 'Impossible de générer la forme hausa pour le moment.';
  } else if (code == 'OUT_OF_RANGE' || status == 400) {
    type = GenerationFailureType.outOfRange;
    message = 'Nombre hors plage. Choisissez un nombre entre 0 et 1 000 000.';
  } else if (code == 'UNRESOLVED_FORM') {
    type = GenerationFailureType.unavailable;
    message = 'Ce nombre n’a pas encore de forme hausa disponible.';
  } else if (status == 422) {
    type = GenerationFailureType.outOfRange;
    message = 'Nombre hors plage. Choisissez un nombre entre 0 et 1 000 000.';
  } else if (status == 500 || status == 503) {
    type = GenerationFailureType.unavailable;
    message = 'Le service est momentanément indisponible.';
  } else {
    type = GenerationFailureType.unknown;
    message = 'Impossible de générer la forme hausa pour le moment.';
  }

  return GenerationFailure(
    type: type,
    message: message,
    statusCode: status,
    code: code,
  );
}
