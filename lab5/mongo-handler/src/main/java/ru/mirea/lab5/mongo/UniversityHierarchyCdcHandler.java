package ru.mirea.lab5.mongo;

import com.mongodb.client.model.DeleteOneModel;
import com.mongodb.client.model.ReplaceOneModel;
import com.mongodb.client.model.ReplaceOptions;
import com.mongodb.client.model.WriteModel;
import com.mongodb.kafka.connect.sink.MongoSinkTopicConfig;
import com.mongodb.kafka.connect.sink.cdc.CdcHandler;
import com.mongodb.kafka.connect.sink.converter.SinkDocument;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import org.bson.BsonDocument;
import org.bson.BsonString;
import org.bson.BsonValue;

/** Builds one embedded university document from Debezium events of three tables. */
public final class UniversityHierarchyCdcHandler extends CdcHandler {
  // MongoDB Sink creates a handler per topic. State must therefore be static
  // to join events from universities, institutes and departments.
  private static final Map<String, BsonDocument> universities = new ConcurrentHashMap<>();
  private static final Map<String, BsonDocument> institutes = new ConcurrentHashMap<>();
  private static final Map<String, BsonDocument> departments = new ConcurrentHashMap<>();

  public UniversityHierarchyCdcHandler(final MongoSinkTopicConfig config) { super(config); }

  @Override
  public Optional<WriteModel<BsonDocument>> handle(final SinkDocument document) {
    BsonDocument event = document.getValueDoc().orElse(null);
    if (event == null || event.isEmpty()) return Optional.empty();
    BsonDocument source = documentOrNull(event, "source");
    BsonValue operation = event.get("op");
    if (source == null || operation == null || !operation.isString()) return Optional.empty();
    String table = string(source, "table");
    boolean deleted = "d".equals(operation.asString().getValue());
    BsonDocument row = documentOrNull(event, deleted ? "before" : "after");
    if (table == null || row == null || string(row, "id") == null) return Optional.empty();
    String id = string(row, "id");
    String universityId;
    switch (table) {
      case "universities":
        universityId = id; update(universities, id, row, deleted);
        if (deleted) return Optional.of(new DeleteOneModel<>(idFilter(universityId)));
        break;
      case "institutes":
        universityId = string(row, "university_id"); update(institutes, id, row, deleted); break;
      case "departments":
        update(departments, id, row, deleted); universityId = universityForInstitute(string(row, "institute_id")); break;
      default: return Optional.empty();
    }
    if (universityId == null || !universities.containsKey(universityId)) return Optional.empty();
    return Optional.of(new ReplaceOneModel<>(idFilter(universityId), render(universityId), new ReplaceOptions().upsert(true)));
  }

  private static void update(Map<String, BsonDocument> map, String id, BsonDocument row, boolean deleted) {
    if (deleted) map.remove(id); else map.put(id, row.clone());
  }
  private String universityForInstitute(String instituteId) {
    BsonDocument institute = institutes.get(instituteId);
    return institute == null ? null : string(institute, "university_id");
  }
  private BsonDocument render(String universityId) {
    BsonDocument root = universities.get(universityId).clone();
    root.put("_id", new BsonString(universityId));
    BsonDocument outInstitutes = new BsonDocument();
    for (BsonDocument institute : institutes.values()) {
      if (!universityId.equals(string(institute, "university_id"))) continue;
      BsonDocument outInstitute = institute.clone(); BsonDocument outDepartments = new BsonDocument();
      for (BsonDocument department : departments.values()) {
        if (!string(institute, "id").equals(string(department, "institute_id"))) continue;
        BsonDocument outDepartment = department.clone();
        outDepartments.put(string(department, "id"), outDepartment);
      }
      outInstitute.put("departments", outDepartments); outInstitutes.put(string(institute, "id"), outInstitute);
    }
    root.put("institutes", outInstitutes); return root;
  }
  private static BsonDocument idFilter(String id) { return new BsonDocument("_id", new BsonString(id)); }
  private static BsonDocument documentOrNull(BsonDocument doc, String field) {
    BsonValue value = doc.get(field); return value != null && value.isDocument() ? value.asDocument() : null;
  }
  private static String string(BsonDocument doc, String field) {
    BsonValue value = doc.get(field); return value != null && value.isString() ? value.asString().getValue() : null;
  }
}
