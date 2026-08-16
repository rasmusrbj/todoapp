import SwiftUI

/// What the list editor was opened for.
struct ListEditorRequest: Identifiable {
    enum Mode {
        case create
        case edit(Todo_V1_TodoList)
    }

    let id = UUID()
    let mode: Mode

    static var create: ListEditorRequest { ListEditorRequest(mode: .create) }
    static func edit(_ list: Todo_V1_TodoList) -> ListEditorRequest {
        ListEditorRequest(mode: .edit(list))
    }
}

/// Creating and renaming a list.
struct ListEditorSheet: View {
    let request: ListEditorRequest

    @Environment(Actions.self) private var actions
    @Environment(\.dismiss) private var dismiss

    @State private var draft: ListDraft
    @State private var isSaving = false

    private let editingId: String?

    init(request: ListEditorRequest) {
        self.request = request
        switch request.mode {
        case .create:
            _draft = State(initialValue: ListDraft())
            self.editingId = nil
        case let .edit(list):
            _draft = State(initialValue: ListDraft(list: list))
            self.editingId = list.id
        }
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("lists.namePlaceholder", text: $draft.name)
                        .font(.body.weight(.medium))
                    TextField("lists.descriptionPlaceholder", text: $draft.description, axis: .vertical)
                        .lineLimit(2...4)
                        .foregroundStyle(Theme.textSecondary)
                }

                Section {
                    ColorSelector(selection: $draft.color)
                } header: {
                    Text("lists.color")
                }

                Section {
                    EnumPicker(title: "lists.visibility", selection: $draft.visibility)
                        .pickerStyle(.inline)
                        .labelsHidden()
                } header: {
                    Text("lists.visibility")
                } footer: {
                    Text(visibilityExplanation)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.background)
            .navigationTitle(editingId == nil ? "lists.newList" : "lists.editList")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("action.cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(editingId == nil ? "action.create" : "action.save") {
                        Task { await save() }
                    }
                    .fontWeight(.semibold)
                    .disabled(!draft.isValid || isSaving)
                }
            }
            .interactiveDismissDisabled(isSaving)
        }
    }

    /// Spells out what the chosen visibility actually means, because "shared" and
    /// "public" are the kind of words everyone assumes they understand differently.
    private var visibilityExplanation: LocalizedStringKey {
        switch draft.visibility {
        case .private: "lists.visibilityPrivateHint"
        case .shared: "lists.visibilitySharedHint"
        case .public: "lists.visibilityPublicHint"
        case .unspecified, .UNRECOGNIZED: ""
        }
    }

    private func save() async {
        isSaving = true
        defer { isSaving = false }
        let saved: Bool
        if let editingId {
            saved = await actions.updateList(draft, id: editingId)
        } else {
            saved = await actions.createList(draft) != nil
        }
        if saved {
            Haptics.success()
            dismiss()
        }
    }
}

/// The list colour palette, as swatches.
///
/// Not a `Picker`: a colour is chosen by looking at it, and a menu that shows the
/// name of a colour instead of the colour is a worse control than seven circles.
struct ColorSelector: View {
    @Binding var selection: Todo_V1_ListColor

    var body: some View {
        FlowLayout(spacing: Theme.Space.md, lineSpacing: Theme.Space.md) {
            ForEach(Todo_V1_ListColor.selectable, id: \.self) { color in
                let isOn = color == selection
                Button {
                    selection = color
                    Haptics.impact(.light)
                } label: {
                    Circle()
                        .fill(color.tint)
                        .frame(width: 30, height: 30)
                        .overlay {
                            if isOn {
                                Image(systemName: "checkmark")
                                    .font(.system(size: 13, weight: .bold))
                                    .foregroundStyle(.white)
                            }
                        }
                        // A ring rather than a size change, so the swatches stay on
                        // their grid when the selection moves.
                        .overlay(
                            Circle()
                                .stroke(isOn ? Theme.textPrimary : Theme.border, lineWidth: isOn ? 2 : 1)
                                .padding(-3)
                        )
                }
                .pressable(0.9)
                .accessibilityLabel(color.displayName)
                .accessibilityAddTraits(isOn ? [.isButton, .isSelected] : .isButton)
            }
        }
        .padding(.vertical, Theme.Space.xs)
    }
}
