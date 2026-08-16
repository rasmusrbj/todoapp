import Observation
import SwiftUI

/// A list's labels: create, rename, recolour, delete.
struct ListLabelsScreen: View {
    let listId: String

    @Environment(TodoSession.self) private var session
    @Environment(Actions.self) private var actions

    @State private var model: LabelsModel?
    @State private var editing: LabelEditorRequest?

    var body: some View {
        ScreenScaffold(refresh: { await model?.load() }) {
            VStack(alignment: .leading, spacing: Theme.Space.lg) {
                if let model {
                    StateView(
                        state: model.state,
                        emptySymbol: "tag",
                        emptyTitle: "lists.noLabelsTitle",
                        emptyMessage: "lists.noLabelsBody",
                        emptyActionTitle: model.canWrite ? "lists.newLabel" : nil,
                        emptyAction: model.canWrite ? { editing = .create(listId: listId) } : nil,
                        retry: { await model.load() }
                    ) { labels in
                        VStack(spacing: 0) {
                            ForEach(Array(labels.enumerated()), id: \.element.id) { index, label in
                                if index > 0 { InsetDivider(leading: Theme.Space.lg) }
                                LabelRow(
                                    label: label,
                                    canWrite: model.canWrite,
                                    onEdit: { editing = .edit(label) }
                                )
                            }
                        }
                        .cardSurface()
                    }
                }
            }
            .padding(.top, Theme.Space.sm)
        }
        .navigationTitle("lists.labels")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if model?.canWrite == true {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { editing = .create(listId: listId) } label: {
                        Image(systemName: "plus")
                    }
                    .accessibilityLabel("lists.newLabel")
                }
            }
        }
        .task {
            if model == nil { model = LabelsModel(backend: session.backend, listId: listId) }
            await model?.load()
        }
        .task(id: actions.revision) {
            guard actions.revision > 0 else { return }
            await model?.load()
        }
        .sheet(item: $editing) { request in
            LabelEditorSheet(request: request)
        }
    }
}

private struct LabelRow: View {
    let label: Todo_V1_Label
    let canWrite: Bool
    let onEdit: () -> Void

    @Environment(Actions.self) private var actions

    var body: some View {
        HStack(spacing: Theme.Space.md) {
            LabelChip(name: label.name, color: label.color)

            Spacer(minLength: Theme.Space.sm)

            // How many tasks carry it — the number that decides whether deleting is
            // harmless or disruptive.
            Text("lists.labelTaskCount \(Int(label.taskCount))")
                .font(.caption)
                .foregroundStyle(Theme.textTertiary)
                .monospacedDigit()

            if canWrite {
                Menu {
                    Button(action: onEdit) {
                        Label("action.edit", systemImage: "pencil")
                    }
                    Button(role: .destructive) {
                        Task { await actions.deleteLabel(id: label.id) }
                    } label: {
                        Label("action.delete", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis")
                        .font(.caption)
                        .foregroundStyle(Theme.textTertiary)
                        .frame(width: 28, height: 28)
                        .contentShape(Rectangle())
                }
                .accessibilityLabel("action.more")
            }
        }
        .padding(.horizontal, Theme.Space.lg)
        .padding(.vertical, Theme.Space.md)
    }
}

struct LabelEditorRequest: Identifiable {
    enum Mode {
        case create(listId: String)
        case edit(Todo_V1_Label)
    }

    let id = UUID()
    let mode: Mode

    static func create(listId: String) -> LabelEditorRequest {
        LabelEditorRequest(mode: .create(listId: listId))
    }

    static func edit(_ label: Todo_V1_Label) -> LabelEditorRequest {
        LabelEditorRequest(mode: .edit(label))
    }
}

private struct LabelEditorSheet: View {
    let request: LabelEditorRequest

    @Environment(Actions.self) private var actions
    @Environment(\.dismiss) private var dismiss

    @State private var name: String
    @State private var color: Todo_V1_ListColor
    @State private var isSaving = false

    private let listId: String?
    private let labelId: String?

    init(request: LabelEditorRequest) {
        self.request = request
        switch request.mode {
        case let .create(listId):
            _name = State(initialValue: "")
            _color = State(initialValue: .blue)
            self.listId = listId
            self.labelId = nil
        case let .edit(label):
            _name = State(initialValue: label.name)
            _color = State(initialValue: label.color)
            self.listId = nil
            self.labelId = label.id
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("lists.labelName", text: $name)
                } footer: {
                    // Names are unique per list, case-insensitively — the server has a
                    // `lower(name)` index for it — so "Urgent" and "urgent" collide.
                    Text("lists.labelNameFooter")
                }
                Section {
                    ColorSelector(selection: $color)
                } header: {
                    Text("lists.color")
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background)
            .navigationTitle(labelId == nil ? "lists.newLabel" : "lists.editLabel")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("action.cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(labelId == nil ? "action.create" : "action.save") {
                        Task { await save() }
                    }
                    .fontWeight(.semibold)
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isSaving)
                }
            }
        }
        .presentationDetents([.medium])
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if let labelId {
            await actions.updateLabel(id: labelId, name: trimmed, color: color)
        } else if let listId {
            guard await actions.createLabel(listId: listId, name: trimmed, color: color) else { return }
        }
        if actions.failure == nil { dismiss() }
    }
}

// MARK: - Model

@MainActor
@Observable
final class LabelsModel {
    private let backend: TodoBackend
    private let listId: String

    private(set) var state: LoadState<[Todo_V1_Label]> = .loading
    private(set) var canWrite = false

    init(backend: TodoBackend, listId: String) {
        self.backend = backend
        self.listId = listId
    }

    func load() async {
        // Two calls, not one: the list carries `LabelRef`s (id, name, colour) but not
        // `task_count`, and the count is the whole point of this screen.
        async let labels = fetchLabels()
        async let role = fetchRole()
        let (loadedLabels, loadedRole) = await (labels, role)
        canWrite = loadedRole?.canWrite ?? false
        state = loadedLabels.listState
    }

    private func fetchLabels() async -> Result<[Todo_V1_Label], AppFailure> {
        let request = Todo_V1_ListLabelsRequest.with { $0.listID = listId }
        return unwrap(await backend.lists.listLabels(request: request)) { $0.labels }
    }

    private func fetchRole() async -> Todo_V1_MemberRole? {
        let request = Todo_V1_GetListRequest.with { $0.id = listId }
        return unwrap(await backend.lists.getList(request: request)) {
            $0.hasList ? $0.list.viewerRole : nil
        }.value
    }
}
